#!/usr/bin/env python3
"""套用、檢查及列出已核可的模型供應商 profile（MYL-129），並留下切換執行單（MYL-131）。

這支工具只讀取 ``.foundry/config.yml`` 既有的 profile；它不建立或修改
profile。供應商到 Paperclip adapterType 的登記表唯一來源是
``probe_providers.PROVIDERS``。

``--apply`` 的稽核落點二選一，兩者都是 ``M6`` 第 1 級的義務落實：
``--issue MYL-nnn`` 把報告貼回既有工單，``--create-issue --parent MYL-nnn``
另開一張切換執行單（描述由 ``templates/switch-execution-issue.md`` 產生）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

import probe_providers as providers


# 這是 C2 補上的「模型層 × 供應商」落點。供應商到 adapterType 不在這裡，
# 必須從 probe_providers.PROVIDERS 取得，避免兩份 adapter 登記表漂移。
#
# 這張表 high 層的 effort 用 `"max"`，**不要改成 `"xhigh"`**（MYL-133 已查證兩邊皆合法）。
# effort 值域的權威歸屬、查證方式，以及「為什麼這裡刻意不做機械驗證」，
# 見 docs/standards/known-drift.md 的 L31——那是唯一一份，不要在這裡再抄一次。
MODEL_TARGETS = {
    "claude": {
        "high": ("claude-opus-5", "max"),
        "medium": ("claude-opus-5", "high"),
        "low": ("claude-sonnet-5", "medium"),
    },
    "codex": {
        "high": ("gpt-5.6-sol", "max"),
        "medium": ("gpt-5.6-terra", "high"),
        "low": ("gpt-5.6-terra", "medium"),
    },
}

M5_GUIDANCE = (
    "依 M5 處置：停止、不重試也不自行改供應商；先執行 "
    "python3 tools/model-routing/probe_providers.py 盤點替代供應商，"
    "提出方案取得裁定，並在裁定中寫明切回原 profile 的時機。"
)
CONFIGURE_AGENTS_ERROR = "本動詞需要 configure_agents，全公司只有 CEO 持有"

# ── 三種結束狀態（`--check` 的第三態，AC 2）─────────────────────────────────
#
# 「讀不到」和「不一致」是兩件事，混成同一個 exit code 的代價很具體：呼叫端（人或
# CI）分不出「平台漂移了、去修」與「這把金鑰看不到、換個身分再看」。2 留給 argparse
# 的用法錯誤，所以第三態用 3。
EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_UNVERIFIABLE = 3

#: 讀不到 `adapterConfig` 時要印的成因與替代路徑。
#:
#: ⚠️ 工具的判準是**看得到的訊號**（回傳的 `adapterConfig` 是空 dict），不是權限鍵。
#: 這是刻意的：授權模型會隨 server build 換（實測跑在 :3100 的
#: `@paperclipai/server` 2026.831.1 走 `access.decide({action:"agent_config:read"})`
#: → `decideWithAgentConfigReadGrant()`，`permissionForAction()` 對該 action 回
#: `null`，根本不走 permissionKey 那條路），拿權限鍵當判準會在下一次 build 靜默失效。
UNVERIFIABLE_GUIDANCE = (
    "成因：平台對「不是自己」的 agent 回的是 HTTP 200，但把 adapterConfig 靜默清成 "
    "`{}`——不是 403，所以看起來像「這個 agent 真的沒設定」。實測的觸發條件是呼叫者"
    "沒有 `agents:configure`（Product Manager／Developer／Code Reviewer 的金鑰都會踩到）。\n"
    "替代路徑：用 CEO 或使用者的 board 金鑰重跑（CEO 自 2026-09-02 持有 "
    "`agents:configure`，逐名實測讀得到完整值）；只想看將送出的內容則跑 `--dry-run`，"
    "那條路徑不需要讀得到現況。\n"
    "⚠️ 本次不列出逐格差異：讀不到不等於不一致，把遮蔽值當實況會是整片假警報。"
)


class UnverifiableError(RuntimeError):
    """讀不到平台實況。與「實況和宣告不一致」分開，才對得上不同的 exit code。"""

# ── C4（MYL-131）：切換執行單 ────────────────────────────────────────────────
# M6 第 1 級的常設授權不是白給的，義務是「留下執行單與逐角色回查證據」。以下這一段
# 就是那份義務的機械落點：報告貼回既有工單（--issue），或另開一張切換執行單（--create-issue）。

#: 切換執行單的描述長什麼樣，只寫在模板裡；本檔不留第二份拷貝。
SWITCH_ISSUE_TEMPLATE = "templates/switch-execution-issue.md"

#: 模板裡「以下才是工單描述」的分界。體例同 repo 雙入口檔的 `FOUNDRY:SHARED-BODY`。
ISSUE_BODY_MARKER = "<!-- FOUNDRY:ISSUE-BODY -->"

PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")
TEMPLATE_TITLE_RE = re.compile(r"(?m)^title:\s*(\S[^\n]*)$")

#: 開單者白名單（protocol 第 1 節 `I1`）。比對的是 `.foundry/org.yml` 的角色 id，
#: **不是**平台的 `role` 欄位——平台那一欄是粗粒度 enum，Product Manager、Product
#: Analyst 與 Scrum Master 同為 `pm`，拿它判等於把白名單放寬給另外兩個角色。
ISSUE_AUTHOR_ROLES = ("ceo", "product-manager")
ISSUE_AUTHOR_ERROR = (
    "開單者白名單見 `I1`：--create-issue 只有 CEO 與 Product Manager 的金鑰送得出建單"
    "請求。本次金鑰解析到的角色是 {role}；要留下這張執行單，把報告交給 Product Manager 開。"
)

#: `--parent` 必填。不給就停在這裡，**不自行宣告頂層單**：那一行寫在描述裡、開單者
#: 本人改得動（可自我特赦），而 protocol 第 1 節的上位單條款（MYL-117 起的 I3）明文
#: 寫著例外不是違規的預設出路。掛不到樹上的正解是把上位單補上，不是替自己開後門。
PARENT_REQUIRED_ERROR = (
    "--create-issue 必須搭配 --parent MYL-nnn：agent 開的每一張單都要掛得到樹上"
    "（protocol 第 1 節上位單條款 I3）。本工具不會自行寫 `**頂層單**：` 宣告替自己"
    "開後門——I3 明文寫著例外不是違規的預設出路，且那行宣告開單者本人改得動、是可"
    "自我特赦的。正解是把上位單補上：切換總是由某一張單觸發的，把那張單填進 --parent。"
)

#: 建單／貼留言之後的鏡像義務。工具刻意不代做，理由寫在訊息裡。
MIRROR_STEPS = """\
## 接下來的鏡像三步（`skills/foundry-platform/adapters/github.md` 時機 1＋時機 3）

本工具刻意不代做：它沒有 `gh` 這條路徑，也不該替執行者判斷內容適不適合公開。
**漏做會讓 `--selfcheck` 的 `mirror-recon` 轉紅、擋住全隊的 commit。**

1. 組鏡像 body：首行 `Foundry-Source: paperclip/{identifier}` → 空行 → 上面那份描述全文
   → 末行唯讀聲明；然後 `gh issue create --title "<標題>" --body-file <檔> --label "<type_label>"`。
2. `gh project item-add <PROJECT> --owner <OWNER> --url <上一步輸出的 issue URL>`。
3. 本單開出來就是 `done`，所以時機 3 的兩件事都要做：project Status 設 `Done` **且**
   `gh issue close <N>`（只做一件 `mirror-recon` 照樣紅）。最後回本單留一則 `Mirrored-to: github#<N>`。
"""


class ApiError(RuntimeError):
    pass


class PaperclipClient:
    """很薄的 HTTP 層，刻意可由測試用 fake 取代。"""

    def __init__(self, base_url=None, api_key=None, company_id=None):
        raw_base = base_url or os.environ.get("PAPERCLIP_API_URL", "")
        self.base_url = raw_base.rstrip("/").removesuffix("/api")
        self.api_key = api_key or os.environ.get("PAPERCLIP_API_KEY", "")
        self.company_id = company_id or os.environ.get("PAPERCLIP_COMPANY_ID", "")
        if not (self.base_url and self.api_key and self.company_id):
            raise ApiError("缺少 PAPERCLIP_API_URL、PAPERCLIP_API_KEY 或 PAPERCLIP_COMPANY_ID")

    def _request(self, method, path, body=None, headers=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                **(headers or {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise ApiError(f"{method} {path} → HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise ApiError(f"{method} {path} 失敗：{error.reason}") from error

    def get(self, path):
        return self._request("GET", path)

    def patch(self, path, body):
        return self._request("PATCH", path, body)

    def post(self, path, body, headers=None):
        return self._request("POST", path, body, headers=headers)


def _now_local():
    """報告與單標題的時間戳。測試一律注入固定值，不讓斷言跟著時鐘漂。

    用**本地時間＋明寫時區位移**，不用 UTC：標題那個日期會被拿去跟 commit、審查報告
    對照，而那些都是本地日期——寫 UTC 會在跨日的那幾個小時裡差一天。
    """
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %z")


def load_yaml(path):
    with Path(path).open(encoding="utf-8") as source:
        return yaml.safe_load(source) or {}


def provider_by_id():
    return {provider["id"]: provider for provider in providers.PROVIDERS}


def effort_key_for(adapter_type):
    """adapterType → 該 adapter **真正消費**的 effort 鍵名。全檔只有這一處。

    組 PATCH body、`--check` 逐格比對、`--apply` 回查三處都走這裡。理由不是省行數，
    是回查的保護力：回查若讀的是「自己剛寫進去的那個鍵」，寫錯鍵時回查照樣相符，
    保護力歸零——2026-09-07 實測，工具兩側都寫死 codex 那個鍵名，而九名 agent 全是
    `claude_local`（讀的是另一個鍵），12 項測試有 10 項照樣綠。

    鍵名本身**一律從登記表取，本檔不留任何字面拷貝**（`test_apply_profile` 有一條
    機械檢查會擋下第二處）。登記表沒寫的 adapterType 一律停下（`L5`）：猜一個鍵寫下去
    不會報錯，只會靜默不生效。
    """
    for provider in providers.PROVIDERS:
        if provider["adapter_type"] != adapter_type:
            continue
        key = provider.get("effort_key")
        if key:
            return key
        raise ValueError(
            f"需人工確認：登記表沒有實證 {adapter_type} 消費哪一個 effort 鍵，"
            "不猜、停止套用（在 probe_providers.PROVIDERS 補上 effort_key 才繼續）"
        )
    raise ValueError(
        f"需人工確認：adapterType {adapter_type!r} 不在 probe_providers 登記表，停止套用"
    )


def role_definitions(org):
    return {role["id"]: role for role in org.get("roles", [])}


def active_profile(config):
    routing = config.get("model_routing")
    if not isinstance(routing, dict):
        raise ValueError(".foundry/config.yml 沒有 model_routing；路由尚未啟用")
    profiles = routing.get("profiles") or {}
    active = routing.get("active")
    if active not in profiles:
        raise ValueError("model_routing.active 沒有指向已登記的 profile")
    return active, profiles[active], profiles


def targets_for_profile(profile, org):
    registry = provider_by_id()
    roles = role_definitions(org)
    profile_roles = profile.get("roles") or {}
    default_provider = profile.get("default_provider")
    if default_provider not in registry:
        raise ValueError(f"profile 的 default_provider 未登記：{default_provider}")

    targets = []
    for role_id, role in roles.items():
        provider_id = profile_roles.get(role_id, default_provider)
        if provider_id not in registry:
            raise ValueError(f"角色 {role_id} 的供應商未登記：{provider_id}")
        tier = role.get("model_tier")
        try:
            model, effort = MODEL_TARGETS[provider_id][tier]
        except KeyError as error:
            raise ValueError(f"沒有 {provider_id}／{tier} 的 model 與 effort 對照") from error
        adapter_type = registry[provider_id]["adapter_type"]
        # 這裡就取一次鍵，是為了讓「登記表沒寫 effort_key」在第一筆 PATCH 之前就炸掉，
        # 而不是套到一半才發現某一家不知道該寫哪個鍵。
        effort_key_for(adapter_type)
        targets.append(
            {
                "role": role_id,
                "provider": provider_id,
                "adapterType": adapter_type,
                "model": model,
                # 刻意叫 `effort` 而不是任何一家的鍵名：目標值是語意，鍵名是 adapter 細節。
                "effort_value": effort,
            }
        )
    return targets


def patch_body(target):
    """L4：只送兩個允許欄位，且 adapterConfig 不攜帶 instructions*。

    ⚠️ 不用 `replaceAdapterConfig: true` 去清舊的死鍵：既有 config 帶 instructions
    bundle 鍵而 body 沒帶時，該旗標會觸發 `assertCanManageInstructionsPath`
    （`agents.ts:1883-1891`），那就是 `L4` 的 403。同 adapterType 走預設的合併語意即可，
    殘留的死鍵無害——沒有 adapter 會讀它。
    """
    return {
        "adapterType": target["adapterType"],
        "adapterConfig": {
            "model": target["model"],
            effort_key_for(target["adapterType"]): target["effort_value"],
        },
    }


def list_agents(client):
    result = client.get(f"/api/companies/{client.company_id}/agents")
    return result.get("agents", []) if isinstance(result, dict) else result


def role_id_for_name(name, org):
    """Paperclip 的顯示名 → Foundry 角色 id；對不上回 None。

    只認 `.foundry/org.yml` 的 `id` 與 `title`。**不看平台的 `role` 欄位**：那一欄是
    粗粒度 enum（Product Manager／Product Analyst／Scrum Master 同為 `pm`），拿它當鍵
    會把三個角色混成一個。
    """
    for role_id, role in role_definitions(org).items():
        if name in {role_id, role.get("title")}:
            return role_id
    return None


def agents_by_role(client, org):
    """Use org.yml titles to map Paperclip display names back to Foundry role IDs."""
    indexed = {}
    for agent in list_agents(client):
        role_id = role_id_for_name(agent.get("name"), org)
        if role_id:
            indexed[role_id] = agent
    return indexed


def assert_registered_current_adapters(client, targets, agents, *, precheck_readback=False):
    """套用前的一次性 GET：`L5` 未知 adapter 不作為首次寫入的試驗對象，順帶做 AC 14 預檢。

    `precheck_readback=True` 時，這一趟同時是「回查能力預檢」：拿到被遮蔽的空
    `adapterConfig` 就地停下。時機是關鍵——這整個迴圈跑在**第一筆 PATCH 之前**，
    所以「這把金鑰回查不成立」會在還沒改任何東西時說出來，而不是套完第 1 個角色、
    回查必然失敗、然後停在一個改到一半的狀態（正是 AC 10 要防的形狀）。
    """
    registered = {provider["adapter_type"] for provider in providers.PROVIDERS}
    current_agents = {}
    for target in targets:
        agent = agents.get(target["role"])
        if not agent:
            raise ValueError(f"平台找不到角色：{target['role']}")
        current = client.get(f"/api/agents/{agent['id']}")
        current_adapter = current.get("adapterType")
        if current_adapter not in registered:
            raise ValueError(
                f"需人工確認：角色 {target['role']} 的 adapterType "
                f"{current_adapter!r} 不在 probe_providers 登記表，停止套用"
            )
        if precheck_readback:
            assert_config_readable(
                current, target["role"],
                phase="`--apply` 預檢中止（一筆 PATCH 都還沒送出）",
            )
        current_agents[target["role"]] = current
    return current_agents


def differs(actual, target):
    """逐格比對，回 `(欄位, 宣告值, 實況值)`。

    effort 那一格兩側取的鍵可以不一樣，而且必須不一樣：宣告值掛在**目標** adapter 的
    鍵上，實況值要從**現況** adapter 真正消費的鍵讀。換型的那一格若兩側都用目標鍵，
    現況 adapter 的舊 effort 會被讀成 `None`——看起來像「沒設定」，其實是讀錯欄位。
    """
    config = actual.get("adapterConfig") or {}
    declared_key = effort_key_for(target["adapterType"])
    live_adapter = actual.get("adapterType")
    try:
        live_key = declared_key if live_adapter == target["adapterType"] else effort_key_for(live_adapter)
    except ValueError:
        # 現況是登記表外的 adapter：`--apply` 早已在 AC 7 停下，這裡只會發生在 `--check`。
        # 讀目標鍵，於是那一格報不符——比靜默把它算成相符誠實。
        live_key = declared_key
    return [
        ("adapterType", target["adapterType"], live_adapter),
        ("adapterConfig.model", target["model"], config.get("model")),
        (f"adapterConfig.{declared_key}", target["effort_value"], config.get(live_key)),
    ]


def assert_config_readable(actual, role, *, phase):
    """拒絕把 API 權限遮蔽的空設定誤當成平台實況（AC 2 第三態、AC 14 預檢）。

    判準是**回傳值的形狀**（`adapterConfig == {}`），不是呼叫者持有哪個權限鍵——理由
    見 `UNVERIFIABLE_GUIDANCE` 的註解。
    """
    if actual.get("adapterConfig") == {}:
        raise UnverifiableError(
            f"{phase}：讀不到角色 {role} 的 adapterConfig（平台回 200 但內容被清空），"
            f"無法回查平台實況。\n{UNVERIFIABLE_GUIDANCE}"
        )


def markdown_value(value):
    if value is None:
        return "—"
    return str(value).replace("|", "\\|")


def print_waiver(profile_name, profile, emit=print):
    if profile.get("waives_m4"):
        emit(f"- active profile：`{profile_name}`；M4 waiver：`true`")
        emit(f"- waiver_reason：{profile.get('waiver_reason', '')}")
    else:
        emit(f"- active profile：`{profile_name}`；M4 waiver：`false`")


def command_list(config):
    active, _, profiles = active_profile(config)
    print(f"目前 active：{active}")
    for name, profile in profiles.items():
        marker = "（active）" if name == active else ""
        print(f"- {name} {marker}".rstrip())
        if profile.get("waives_m4"):
            print(f"  waives_m4: true\n  waiver_reason: {profile.get('waiver_reason', '')}")
        else:
            print("  waives_m4: false")
    return 0


def command_check(client, config, org):
    profile_name, profile, _ = active_profile(config)
    targets = targets_for_profile(profile, org)
    agents = agents_by_role(client, org)
    differences = []
    print("## 模型路由對帳")
    print_waiver(profile_name, profile)
    for target in targets:
        agent = agents.get(target["role"])
        if not agent:
            differences.append((target["role"], "agent", "已宣告", "平台找不到"))
            continue
        actual = client.get(f"/api/agents/{agent['id']}")
        assert_config_readable(actual, target["role"], phase="`--check` 對帳中止")
        for field, declared, live in differs(actual, target):
            if declared != live:
                differences.append((target["role"], field, declared, live))
    if not differences:
        print("✅ 平台實況與 active profile 一致")
        return EXIT_OK
    print("❌ 平台實況與 active profile 不一致：")
    print("| 角色 | 欄位 | 宣告值 | 實況值 |\n| --- | --- | --- | --- |")
    for role, field, declared, live in differences:
        print(f"| {role} | {field} | `{markdown_value(declared)}` | `{markdown_value(live)}` |")
    return EXIT_DRIFT


def command_dry_run(client, profile_name, profiles, org):
    if profile_name not in profiles:
        raise ValueError(f"未登記的 profile：{profile_name}")
    agents = agents_by_role(client, org)
    for target in targets_for_profile(profiles[profile_name], org):
        agent = agents.get(target["role"])
        if not agent:
            raise ValueError(f"平台找不到角色：{target['role']}")
        print(f"PATCH agent {target['role']} ({agent['id']})")
        print(json.dumps(patch_body(target), ensure_ascii=False, sort_keys=True))
    return 0


def is_ceo(me):
    return me.get("name") == "ceo" or me.get("role") == "ceo"


def ensure_ready(targets, probe_all=providers.probe_all):
    results = probe_all()
    ready = set(providers.ready_ids(results))
    missing = sorted({target["provider"] for target in targets} - ready)
    if missing:
        raise ValueError(f"目標 profile 的供應商不可用：{'、'.join(missing)}。\n{M5_GUIDANCE}")
    return results


def update_active_config(path, profile_name):
    """M6 第 1 級唯一允許的 repo 設定寫入：只換 active 指標。

    判準是**正規表示式有沒有配到那一行**，不是「改完之後內容有沒有變」。差別在套用
    「已經是 active 的那個 profile」時：`active:` 那行找得到、只是替換結果與原文相同。
    拿「內容沒變」當失敗，就會在一次完全成功的冪等重跑之後，帶著「設定檔壞了」的訊息
    非零 exit——而這個函式跑在**所有 PATCH 送完並逐格回查通過之後**，平台其實已經寫
    進去了，只是成功那一行永遠印不出來。
    """
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    section = re.compile(r"(?ms)^(model_routing:\n.*?)(?=^\S|\Z)")
    matched = section.search(text)
    if not matched:
        raise ValueError("找不到 model_routing 段，拒絕改寫 active")
    rewritten, replaced = re.subn(
        r"(?m)^(  active:)\s*[^\n]*$", rf"\1 {profile_name}", matched.group(1), count=1)
    if not replaced:
        raise ValueError("找不到 model_routing.active，拒絕改寫")
    config_path.write_text(text[: matched.start(1)] + rewritten + text[matched.end(1) :], encoding="utf-8")


def print_transition(targets, current_agents, emit=print):
    emit("## 逐角色現值 → 目標值")
    emit("| 角色 | 欄位 | 現值 | 目標值 |")
    emit("| --- | --- | --- | --- |")
    for target in targets:
        current = current_agents[target["role"]]
        for field, target_value, current_value in differs(current, target):
            emit(
                f"| {target['role']} | {field} | `{markdown_value(current_value)}` "
                f"| `{markdown_value(target_value)}` |"
            )


def print_verification(role, actual, target, emit=print):
    emit(f"### 回查：{role}")
    emit("| 欄位 | 目標值 | 回查值 | 結果 |")
    emit("| --- | --- | --- | --- |")
    mismatches = []
    for field, expected, live in differs(actual, target):
        ok = expected == live
        emit(
            f"| {field} | `{markdown_value(expected)}` | `{markdown_value(live)}` "
            f"| {'✅' if ok else '❌'} |"
        )
        if not ok:
            mismatches.append((field, expected, live))
    return mismatches


class Report:
    """執行報告：一邊印給執行者看，一邊留一份好貼回工單／放進新單描述。

    `echo=False` 是給 `--dry-run --create-issue` 用的——那條路徑要印的是**整份描述**，
    報告已經在描述裡了，再印一次等於同一份東西輸出兩遍。
    """

    def __init__(self, echo=True):
        self.echo = echo
        self.lines = []

    def emit(self, text=""):
        if self.echo:
            print(text)
        self.lines.append(text)

    def text(self):
        return "\n".join(self.lines).strip() + "\n"


def rollback_command(previous_active, issue=None, parent=None):
    """`M5`(d)：臨時改派要寫明怎麼改回來，所以回退指令要能原樣複製執行。

    兩條路徑的回退指令不一樣——貼回既有工單的那條回退時仍貼回同一張單；開執行單的那條
    回退時要再開一張（回退本身也是一次切換，也要留下自己的稽核紀錄）。
    """
    tail = f"--issue {issue}" if issue else f"--create-issue --parent {parent}"
    return (
        "python3 tools/model-routing/apply_profile.py "
        f"--profile {previous_active} --apply {tail}"
    )


def emit_report_head(report, *, previous_active, profile_name, profile, probe_results,
                     targets, current_agents, rollback, issue=None, parent=None):
    """報告的前半段：兩條路徑（貼留言／開新單）與預演都共用同一份形狀。"""
    report.emit("# 模型 profile 套用執行報告")
    if issue:
        report.emit(f"- 工單：{issue}")
    else:
        report.emit(f"- 上位單：{parent}（本份報告放進新開的切換執行單）")
    report.emit("- 授權：M6 第 1 級；依 MYL-125 計畫修訂 2 的已核可 profile 切換")
    report.emit(f"- active：`{previous_active}` → `{profile_name}`")
    print_waiver(profile_name, profile, emit=report.emit)
    report.emit("## 供應商盤點（原始輸出）")
    report.emit(providers.render_text(probe_results))
    print_transition(targets, current_agents, emit=report.emit)
    report.emit("## 回退")
    report.emit(f"回退指令：{rollback}")


def open_questions(profile_name, profile):
    """第 1 節四段骨架的第四段：沒有就明確寫「無」，不留空。

    waiver **不是**未決事項：它是已經拍過板的取捨，改回條件寫在報告的 waiver 段。
    寫成未決事項會讓這張單一開出來就違反「有未解未決事項不得進入實作」。
    """
    if profile.get("waives_m4"):
        return (
            f"無。（`{profile_name}` 掛有 `M4` waiver，改回條件寫在下方報告的 waiver 段"
            "——那是常設追蹤事項，不是本單的未決問題。）"
        )
    return "無"


def load_switch_template(path):
    """模板 → `(標題模板, 描述模板)`。形狀壞掉一律報錯，不猜。"""
    text = Path(path).read_text(encoding="utf-8")
    occurrences = text.count(ISSUE_BODY_MARKER)
    if occurrences == 0:
        raise ValueError(f"{path} 找不到 {ISSUE_BODY_MARKER}，讀不出工單描述從哪一行開始")
    # 出現兩次是**靜默**的壞法：切在第一次，說明段的後半會跟著進工單描述，而產出的單
    # 看起來只是「開頭多了幾句說明」。所以這裡報錯，不猜哪一個才是真的分界。
    if occurrences > 1:
        raise ValueError(
            f"{path} 出現 {occurrences} 次 {ISSUE_BODY_MARKER}；分界只能有一個，"
            "說明段要提到它請不要寫出完整標記"
        )
    head, body = text.split(ISSUE_BODY_MARKER, 1)
    matched = TEMPLATE_TITLE_RE.search(head)
    if not matched:
        raise ValueError(f"{path} 的 frontmatter 缺少 `title:` 那一行")
    return matched.group(1).strip(), body.strip() + "\n"


def render_template(template, values):
    def substitute(match):
        key = match.group(1)
        if key not in values:
            raise ValueError(f"模板佔位符 {{{{{key}}}}} 沒有對應值，拒絕送出半成品")
        return str(values[key])

    rendered = PLACEHOLDER_RE.sub(substitute, template)
    # 漏填是報錯不是照送：`{{…}}` 出現在平台上的單裡，讀的人分不出那是沒填還是原文。
    if "{{" in rendered:
        raise ValueError("模板填完仍留有 `{{` 佔位符，拒絕送出半成品")
    return rendered


def assert_issue_author(me, org):
    """`I1` 開單者白名單。在第一筆寫入之前跑——套完才發現留不下紀錄，等於改了平台卻沒有稽核證據。"""
    role_id = role_id_for_name(me.get("name"), org)
    if role_id not in ISSUE_AUTHOR_ROLES:
        raise ValueError(ISSUE_AUTHOR_ERROR.format(role=role_id or me.get("name")))
    return role_id


def fetch_parent_issue(client, parent):
    """`--parent` 是必填，且要真的讀得到——UUID 是掛上位單唯一吃得下的形狀。"""
    if not parent:
        raise ValueError(PARENT_REQUIRED_ERROR)
    issue = client.get(f"/api/issues/{parent}")
    if not issue.get("id"):
        raise ValueError(f"--parent {parent} 讀不到 UUID，無法掛上位單")
    return issue


def build_switch_issue_payload(template_path, values, *, parent_issue, assignee_agent_id):
    """組建單 payload。`I2` 的四欄在這裡一次備齊，反向那一格在下面被守住。"""
    title_template, body_template = load_switch_template(template_path)
    payload = {
        "title": render_template(title_template, values),
        "description": render_template(body_template, values),
        # `I2` 上位單那一欄。用 `POST /companies/{id}/issues` 而不是 `/children` 捷徑，
        # 是因為 `createChildIssueSchema` 把 `parentId` omit 掉了（zod 對未宣告鍵是
        # strip 不是報錯）——走那條路 parentId 只存在於 URL，payload 上斷言不到。
        "parentId": parent_issue["id"],
        # `I2` 指派對象那一欄。指給執行者自己：切換已經做完，這張單的擁有者就是做的人。
        "assigneeAgentId": assignee_agent_id,
        # 一開出來就是 `done`：套用與回查在開單之前跑完，描述裡每一條 AC 當下都已成立。
        # 開成 `todo` 會多喚醒一個 agent 去做一件做完的事。
        "status": "done",
        "priority": "low",
        "workMode": "standard",
    }
    if parent_issue.get("projectId"):
        payload["projectId"] = parent_issue["projectId"]
    assert_parent_not_blocker(payload)
    return payload


def assert_parent_not_blocker(payload):
    """`I2` 反向那一格：上位單不得同時被填進上游依賴。

    平台不擋這件事（它的守衛只看不得自我阻擋、必須同公司、依賴圖不得成環），但母單多半
    要等子單做完才結 ⇒ 把母單掛成自己的 blocker 就是做出一張再也不會被叫醒的單。
    """
    parent = payload.get("parentId")
    if parent and parent in (payload.get("blockedByIssueIds") or []):
        raise ValueError("上位單被填進 blockedByIssueIds，會做出一張醒不來的單，拒絕建單")


def run_id_headers():
    """`X-Paperclip-Run-Id` 讓寫入歸屬到當次 run；環境沒給就不硬塞空值。"""
    run_id = os.environ.get("PAPERCLIP_RUN_ID")
    return {"X-Paperclip-Run-Id": run_id} if run_id else {}


def post_report_comment(client, issue, body):
    """把報告貼回既有工單，並回讀查證未被截斷。

    ⚠️ `GET /api/issues/<ID>/comments` 回的陣列是**新到舊**（index 0 才是最新），
    2026-09-07 實測。所以這裡優先按 POST 回傳的 id 單筆回讀，位置只是退路。
    """
    created = client.post(f"/api/issues/{issue}/comments", {"body": body}, headers=run_id_headers())
    comment_id = (created or {}).get("id")
    if comment_id:
        fetched = client.get(f"/api/issues/{issue}/comments/{comment_id}")
    else:
        comments = client.get(f"/api/issues/{issue}/comments") or []
        fetched = comments[0] if comments else {}
    if (fetched or {}).get("body") != body:
        raise ValueError(
            f"回讀 {issue} 的留言與送出的內容不一致（可能被截斷）："
            f"送出 {len(body)} 字，讀回 {len((fetched or {}).get('body') or '')} 字"
        )
    print(f"\n✅ 執行報告已貼回 {issue}（留言 {comment_id or '（無 id，按位置回讀）'}），回讀未截斷")
    return fetched


def create_switch_issue(client, payload):
    """建切換執行單並回讀查證四欄與描述完整性。"""
    created = client.post(f"/api/companies/{client.company_id}/issues", payload)
    identifier = (created or {}).get("identifier")
    if not identifier:
        raise ValueError(f"建單回應沒有 identifier，無法查證：{created}")
    fetched = client.get(f"/api/issues/{identifier}")
    for field in ("parentId", "assigneeAgentId"):
        if fetched.get(field) != payload[field]:
            raise ValueError(
                f"{identifier} 回讀 {field} 不符：送出 {payload[field]!r}、讀回 {fetched.get(field)!r}"
            )
    if fetched.get("description") != payload["description"]:
        raise ValueError(
            f"{identifier} 回讀描述與送出的不一致（可能被截斷）："
            f"送出 {len(payload['description'])} 字，讀回 {len(fetched.get('description') or '')} 字"
        )
    print(f"\n✅ 切換執行單已建立：{identifier}（parentId、assigneeAgentId、描述皆回讀相符）")
    print(MIRROR_STEPS.format(identifier=identifier))
    return created


def switch_issue_values(*, profile_name, previous_active, profile, executor, targets,
                        rollback, parent, report_text, applied_at):
    return {
        "profile": profile_name,
        "previous_active": previous_active,
        "applied_at": applied_at,
        "applied_date": applied_at[:10],
        "executor": executor.get("title") or executor.get("name") or "（未知）",
        "executor_agent_id": executor.get("id") or "（未知）",
        "parent": parent,
        "role_count": len(targets),
        "rollback": rollback,
        "open_questions": open_questions(profile_name, profile),
        "report": report_text,
    }


def command_apply(client, profile_name, config_path, profiles, org, issue=None,
                  probe_all=providers.probe_all, create_issue=False, parent=None,
                  template_path=SWITCH_ISSUE_TEMPLATE, now=None):
    if profile_name not in profiles:
        raise ValueError(f"未登記的 profile：{profile_name}")
    me = client.get("/api/agents/me")
    if not is_ceo(me):
        raise ValueError(CONFIGURE_AGENTS_ERROR)
    parent_issue = None
    if create_issue:
        # 白名單與 --parent 都在第一筆 PATCH 之前收掉。順序有意義：套完 8 個角色才發現
        # 建不了單，就是「平台改了、稽核證據沒有」——M6 第 1 級的義務正好落空。
        assert_issue_author(me, org)
        parent_issue = fetch_parent_issue(client, parent)
    previous_active = active_profile(load_yaml(config_path))[0]
    targets = targets_for_profile(profiles[profile_name], org)
    probe_results = ensure_ready(targets, probe_all=probe_all)
    agents = agents_by_role(client, org)
    # 所有未知 adapter 都在第一筆 PATCH 前收掉，不能邊套邊發現；AC 14 的回查能力預檢
    # 搭同一趟 GET，理由見該函式 docstring。
    current_agents = assert_registered_current_adapters(
        client, targets, agents, precheck_readback=True)

    # 在第一筆 PATCH 前印出：後續任一寫入或回查失敗時，仍有可貼回工單的回退方式。
    rollback = rollback_command(previous_active, issue=issue, parent=parent)
    report = Report()
    emit_report_head(
        report, previous_active=previous_active, profile_name=profile_name,
        profile=profiles[profile_name], probe_results=probe_results, targets=targets,
        current_agents=current_agents, rollback=rollback, issue=issue, parent=parent,
    )
    report.emit("## 逐角色回查")

    for target in targets:
        agent = agents[target["role"]]
        client.patch(f"/api/agents/{agent['id']}", patch_body(target))
        actual = client.get(f"/api/agents/{agent['id']}")
        assert_config_readable(actual, target["role"], phase="`--apply` 回查中止")
        mismatches = print_verification(target["role"], actual, target, emit=report.emit)
        if mismatches:
            field, declared, live = mismatches[0]
            raise ValueError(
                f"回查不符，停止於 {target['role']}：{field} 宣告={declared!r} 實況={live!r}"
            )

    update_active_config(config_path, profile_name)
    report.emit("")
    report.emit("✅ 全部角色已套用、逐格回查，並已更新 model_routing.active")

    if issue:
        post_report_comment(client, issue, report.text())
    if create_issue:
        values = switch_issue_values(
            profile_name=profile_name, previous_active=previous_active,
            profile=profiles[profile_name], executor=me, targets=targets,
            rollback=rollback, parent=parent, report_text=report.text(),
            applied_at=now or _now_local(),
        )
        payload = build_switch_issue_payload(
            template_path, values, parent_issue=parent_issue, assignee_agent_id=me["id"],
        )
        create_switch_issue(client, payload)
    return 0


def command_create_issue_dry_run(client, profile_name, config, profiles, org, parent,
                                 template_path=SWITCH_ISSUE_TEMPLATE,
                                 probe_all=providers.probe_all, now=None):
    """印出將建的單的標題與完整描述，**零寫入**。

    刻意不擋非白名單金鑰：預演只讀不寫，任何人都該看得到這張單會長什麼樣；但會警告
    真的建單會被 `I1` 擋下，免得預演綠了才在寫入那一步撞牆。
    """
    if profile_name not in profiles:
        raise ValueError(f"未登記的 profile：{profile_name}")
    me = client.get("/api/agents/me")
    parent_issue = fetch_parent_issue(client, parent)
    previous_active = active_profile(config)[0]
    targets = targets_for_profile(profiles[profile_name], org)
    probe_results = ensure_ready(targets, probe_all=probe_all)
    agents = agents_by_role(client, org)
    current_agents = assert_registered_current_adapters(client, targets, agents)

    rollback = rollback_command(previous_active, parent=parent)
    report = Report(echo=False)
    emit_report_head(
        report, previous_active=previous_active, profile_name=profile_name,
        profile=profiles[profile_name], probe_results=probe_results, targets=targets,
        current_agents=current_agents, rollback=rollback, parent=parent,
    )
    report.emit("## 逐角色回查")
    report.emit("⚠️ `--dry-run` 預演：一筆 PATCH 都還沒送出，所以還沒有回查證據。")
    report.emit(
        f"實際套用時這一段會有 {len(targets)} 個 `### 回查：<角色>` 小節，"
        "逐格列出目標值、回查值與結果。"
    )

    values = switch_issue_values(
        profile_name=profile_name, previous_active=previous_active,
        profile=profiles[profile_name], executor=me, targets=targets,
        rollback=rollback, parent=parent, report_text=report.text(),
        applied_at=now or _now_local(),
    )
    payload = build_switch_issue_payload(
        template_path, values, parent_issue=parent_issue, assignee_agent_id=me.get("id"),
    )

    print("## --create-issue --dry-run 預演（零寫入）")
    role_id = role_id_for_name(me.get("name"), org)
    if role_id not in ISSUE_AUTHOR_ROLES:
        print(f"⚠️ {ISSUE_AUTHOR_ERROR.format(role=role_id or me.get('name'))}")
    print(f"標題：{payload['title']}")
    print(
        f"status：{payload['status']}｜assigneeAgentId：{payload['assigneeAgentId']}"
        f"｜parentId：{payload['parentId']}｜blockedByIssueIds：（不填，見 I2 反向那一格）"
    )
    print("描述：")
    print(payload["description"])
    print(MIRROR_STEPS.format(identifier="<新單編號>"))
    return 0


def parse_args(argv):
    parser = argparse.ArgumentParser(description="套用或對帳已核可的模型供應商 profile")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true")
    action.add_argument("--check", action="store_true")
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--apply", action="store_true")
    parser.add_argument("--profile")
    parser.add_argument("--issue", help="--apply 的稽核報告貼回哪一張既有工單，例如 MYL-129")
    parser.add_argument(
        "--create-issue", action="store_true",
        help="另開一張切換執行單放執行報告（M6 第 1 級的稽核義務）；必須搭配 --parent",
    )
    parser.add_argument("--parent", help="--create-issue 的上位單，例如 MYL-125（必填）")
    parser.add_argument("--config", default=".foundry/config.yml", help=argparse.SUPPRESS)
    parser.add_argument("--org-config", default=".foundry/org.yml", help=argparse.SUPPRESS)
    parser.add_argument("--template", default=SWITCH_ISSUE_TEMPLATE, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def run(args, client=None, probe_all=providers.probe_all, now=None):
    config = load_yaml(args.config)
    org = load_yaml(args.org_config)
    if args.list:
        return command_list(config)
    if args.dry_run or args.apply:
        if not args.profile:
            raise ValueError("--dry-run／--apply 必須搭配 --profile <名>")
    if args.create_issue:
        if not (args.dry_run or args.apply):
            raise ValueError("--create-issue 只搭配 --apply 或 --dry-run 使用")
        if not args.parent:
            raise ValueError(PARENT_REQUIRED_ERROR)
    if args.apply and not (args.issue or args.create_issue):
        raise ValueError(
            "--apply 必須搭配 --issue MYL-nnn（貼回既有工單）或 "
            "--create-issue --parent MYL-nnn（另開執行單），供執行報告與回退指令稽核"
        )
    _, _, profiles = active_profile(config)
    client = client or PaperclipClient()
    if args.check:
        return command_check(client, config, org)
    if args.dry_run:
        if args.create_issue:
            return command_create_issue_dry_run(
                client, args.profile, config, profiles, org, args.parent,
                template_path=args.template, probe_all=probe_all, now=now,
            )
        return command_dry_run(client, args.profile, profiles, org)
    return command_apply(
        client, args.profile, args.config, profiles, org, args.issue, probe_all=probe_all,
        create_issue=args.create_issue, parent=args.parent, template_path=args.template,
        now=now,
    )


def main(argv=None):
    try:
        return run(parse_args(argv if argv is not None else sys.argv[1:]))
    except UnverifiableError as error:
        # 第三態要有自己的 exit code，呼叫端才分得出「去修平台」與「換個身分再看」。
        print(f"❓ 無法驗證：{error}", file=sys.stderr)
        return EXIT_UNVERIFIABLE
    except (ApiError, ValueError) as error:
        print(f"錯誤：{error}", file=sys.stderr)
        return EXIT_DRIFT


if __name__ == "__main__":
    raise SystemExit(main())
