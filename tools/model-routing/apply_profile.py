#!/usr/bin/env python3
"""套用、檢查及列出已核可的模型供應商 profile（MYL-129）。

這支工具只讀取 ``.foundry/config.yml`` 既有的 profile；它不建立或修改
profile。供應商到 Paperclip adapterType 的登記表唯一來源是
``probe_providers.PROVIDERS``。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

import probe_providers as providers


# 這是 C2 補上的「模型層 × 供應商」落點。供應商到 adapterType 不在這裡，
# 必須從 probe_providers.PROVIDERS 取得，避免兩份 adapter 登記表漂移。
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

    def _request(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
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


def load_yaml(path):
    with Path(path).open(encoding="utf-8") as source:
        return yaml.safe_load(source) or {}


def provider_by_id():
    return {provider["id"]: provider for provider in providers.PROVIDERS}


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
        targets.append(
            {
                "role": role_id,
                "provider": provider_id,
                "adapterType": registry[provider_id]["adapter_type"],
                "model": model,
                "modelReasoningEffort": effort,
            }
        )
    return targets


def patch_body(target):
    """L4：只送兩個允許欄位，且 adapterConfig 不攜帶 instructions*。"""
    return {
        "adapterType": target["adapterType"],
        "adapterConfig": {
            "model": target["model"],
            "modelReasoningEffort": target["modelReasoningEffort"],
        },
    }


def list_agents(client):
    result = client.get(f"/api/companies/{client.company_id}/agents")
    return result.get("agents", []) if isinstance(result, dict) else result


def agents_by_role(client, org):
    """Use org.yml titles to map Paperclip display names back to Foundry role IDs."""
    declared = role_definitions(org)
    indexed = {}
    for agent in list_agents(client):
        for role_id, role in declared.items():
            if agent.get("name") in {role_id, role.get("title")}:
                indexed[role_id] = agent
    return indexed


def assert_registered_current_adapters(client, targets, agents):
    """L5：未知既有 adapter 不作為首次寫入的試驗對象。"""
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
        current_agents[target["role"]] = current
    return current_agents


def differs(actual, target):
    config = actual.get("adapterConfig") or {}
    return [
        ("adapterType", target["adapterType"], actual.get("adapterType")),
        ("adapterConfig.model", target["model"], config.get("model")),
        (
            "adapterConfig.modelReasoningEffort",
            target["modelReasoningEffort"],
            config.get("modelReasoningEffort"),
        ),
    ]


def readable_adapter_config(actual, role):
    """拒絕把 API 權限遮蔽的空設定誤當成平台實況。"""
    if actual.get("adapterConfig") == {}:
        raise ValueError(
            f"無法讀取角色 {role} 的完整 adapterConfig（權限遮蔽）；"
            "需要可讀全體 agent 設定的身分，停止對帳，未將遮蔽值列為平台漂移"
        )


def markdown_value(value):
    if value is None:
        return "—"
    return str(value).replace("|", "\\|")


def print_waiver(profile_name, profile):
    if profile.get("waives_m4"):
        print(f"- active profile：`{profile_name}`；M4 waiver：`true`")
        print(f"- waiver_reason：{profile.get('waiver_reason', '')}")
    else:
        print(f"- active profile：`{profile_name}`；M4 waiver：`false`")


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
        readable_adapter_config(actual, target["role"])
        for field, declared, live in differs(actual, target):
            if declared != live:
                differences.append((target["role"], field, declared, live))
    if not differences:
        print("✅ 平台實況與 active profile 一致")
        return 0
    print("❌ 平台實況與 active profile 不一致：")
    print("| 角色 | 欄位 | 宣告值 | 實況值 |\n| --- | --- | --- | --- |")
    for role, field, declared, live in differences:
        print(f"| {role} | {field} | `{declared}` | `{live}` |")
    return 1


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
    """M6 第 1 級唯一允許的 repo 設定寫入：只換 active 指標。"""
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    section = re.compile(r"(?ms)^(model_routing:\n.*?)(?=^\S|\Z)")
    matched = section.search(text)
    if not matched:
        raise ValueError("找不到 model_routing 段，拒絕改寫 active")
    rewritten = re.sub(r"(?m)^(  active:)\s*[^\n]*$", rf"\1 {profile_name}", matched.group(1), count=1)
    if rewritten == matched.group(1):
        raise ValueError("找不到 model_routing.active，拒絕改寫")
    config_path.write_text(text[: matched.start(1)] + rewritten + text[matched.end(1) :], encoding="utf-8")


def print_transition(targets, current_agents):
    print("## 逐角色現值 → 目標值")
    print("| 角色 | 欄位 | 現值 | 目標值 |")
    print("| --- | --- | --- | --- |")
    for target in targets:
        current = current_agents[target["role"]]
        for field, target_value, current_value in differs(current, target):
            print(
                f"| {target['role']} | {field} | `{markdown_value(current_value)}` "
                f"| `{markdown_value(target_value)}` |"
            )


def print_verification(role, actual, target):
    print(f"### 回查：{role}")
    print("| 欄位 | 目標值 | 回查值 | 結果 |")
    print("| --- | --- | --- | --- |")
    mismatches = []
    for field, expected, live in differs(actual, target):
        ok = expected == live
        print(
            f"| {field} | `{markdown_value(expected)}` | `{markdown_value(live)}` "
            f"| {'✅' if ok else '❌'} |"
        )
        if not ok:
            mismatches.append((field, expected, live))
    return mismatches


def command_apply(client, profile_name, config_path, profiles, org, issue, probe_all=providers.probe_all):
    if profile_name not in profiles:
        raise ValueError(f"未登記的 profile：{profile_name}")
    me = client.get("/api/agents/me")
    if not is_ceo(me):
        raise ValueError(CONFIGURE_AGENTS_ERROR)
    previous_active = active_profile(load_yaml(config_path))[0]
    targets = targets_for_profile(profiles[profile_name], org)
    probe_results = ensure_ready(targets, probe_all=probe_all)
    agents = agents_by_role(client, org)
    # 所有未知 adapter 都在第一筆 PATCH 前收掉，不能邊套邊發現。
    current_agents = assert_registered_current_adapters(client, targets, agents)

    # 在第一筆 PATCH 前印出：後續任一寫入或回查失敗時，仍有可貼回工單的回退方式。
    rollback = (
        "python3 tools/model-routing/apply_profile.py "
        f"--profile {previous_active} --apply --issue {issue}"
    )
    print("# 模型 profile 套用執行報告")
    print(f"- 工單：{issue}")
    print("- 授權：M6 第 1 級；依 MYL-125 計畫修訂 2 的已核可 profile 切換")
    print(f"- active：`{previous_active}` → `{profile_name}`")
    print_waiver(profile_name, profiles[profile_name])
    print("## 供應商盤點（原始輸出）")
    print(providers.render_text(probe_results))
    print_transition(targets, current_agents)
    print("## 回退")
    print(f"回退指令：{rollback}")
    print("## 逐角色回查")

    for target in targets:
        agent = agents[target["role"]]
        client.patch(f"/api/agents/{agent['id']}", patch_body(target))
        actual = client.get(f"/api/agents/{agent['id']}")
        readable_adapter_config(actual, target["role"])
        mismatches = print_verification(target["role"], actual, target)
        if mismatches:
            field, declared, live = mismatches[0]
            raise ValueError(
                f"回查不符，停止於 {target['role']}：{field} 宣告={declared!r} 實況={live!r}"
            )

    update_active_config(config_path, profile_name)
    print("\n✅ 全部角色已套用、逐格回查，並已更新 model_routing.active")
    return 0


def parse_args(argv):
    parser = argparse.ArgumentParser(description="套用或對帳已核可的模型供應商 profile")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true")
    action.add_argument("--check", action="store_true")
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--apply", action="store_true")
    parser.add_argument("--profile")
    parser.add_argument("--issue", help="--apply 的稽核報告所屬工單，例如 MYL-129")
    parser.add_argument("--config", default=".foundry/config.yml", help=argparse.SUPPRESS)
    parser.add_argument("--org-config", default=".foundry/org.yml", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def run(args, client=None, probe_all=providers.probe_all):
    config = load_yaml(args.config)
    org = load_yaml(args.org_config)
    if args.list:
        return command_list(config)
    if args.dry_run or args.apply:
        if not args.profile:
            raise ValueError("--dry-run／--apply 必須搭配 --profile <名>")
    if args.apply and not args.issue:
        raise ValueError("--apply 必須搭配 --issue MYL-nnn，供執行報告與回退指令稽核")
    _, _, profiles = active_profile(config)
    client = client or PaperclipClient()
    if args.check:
        return command_check(client, config, org)
    if args.dry_run:
        return command_dry_run(client, args.profile, profiles, org)
    return command_apply(
        client, args.profile, args.config, profiles, org, args.issue, probe_all=probe_all
    )


def main(argv=None):
    try:
        return run(parse_args(argv if argv is not None else sys.argv[1:]))
    except (ApiError, ValueError) as error:
        print(f"錯誤：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
