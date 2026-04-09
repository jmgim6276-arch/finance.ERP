#!/usr/bin/env python3

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path


def resolve_browser_session_dir():
    candidates = [
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent / "scripts",
        Path("/Users/mac/Documents/Playground/agent2-import-run/agent2.2-caishui-fymb-czai-agent2.2-fyong-czai/scripts"),
    ]
    env_path = Path(sys.argv[0]).resolve().parent if sys.argv and sys.argv[0] else None
    if env_path is not None:
        candidates.insert(0, env_path)
    for candidate in candidates:
        if (candidate / "browser_session.py").exists():
            return candidate
    raise RuntimeError("找不到 browser_session.py。请把它放到脚本同目录，或放到 scripts/ 子目录。")


SCRIPT_DIR = resolve_browser_session_dir()
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from browser_session import cdp_eval, ensure_cst_page, find_or_launch_browser  # noqa: E402


BASE_URL = "https://cst.uf-tree.com"


def normalize_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value)).strip()


def unique_index(items, key_fn):
    buckets = defaultdict(list)
    for item in items:
        key = key_fn(item)
        if key:
            buckets[key].append(item)
    return {key: values[0] for key, values in buckets.items() if len(values) == 1}


def choose_parallel_exact_candidate(short_value, full_value, master_index):
    short_key = normalize_text(short_value)
    full_key = normalize_text(full_value)
    short_candidate = master_index.get(short_key) if short_key else None
    full_candidate = master_index.get(full_key) if full_key else None

    if short_candidate and full_candidate and short_candidate["id"] != full_candidate["id"]:
        return None, "ambiguous"
    if full_candidate:
        return full_candidate, "full_exact"
    if short_candidate:
        return short_candidate, "name_exact"
    return None, "no_match"


class CSTBrowserRunner:
    def __init__(self, browser_name="edge", settle_seconds=5):
        self.browser = find_or_launch_browser(preferred=browser_name, target_url=f"{BASE_URL}/index")
        if not self.browser:
            raise RuntimeError("未找到可用浏览器。")
        self.page = ensure_cst_page(self.browser, url=f"{BASE_URL}/index")
        self.settle_seconds = settle_seconds

    def navigate(self, route_name):
        route_url = f"{BASE_URL}/erp/erpArchiveSetting?name={route_name}"
        self.eval(f"location.href={json.dumps(route_url)}; 'ok'")
        deadline = time.time() + 20
        while time.time() < deadline:
            href = self.eval("location.href")
            if f"name={route_name}" in str(href):
                break
            time.sleep(0.5)
        time.sleep(self.settle_seconds)

    def eval(self, expression, await_promise=False):
        return cdp_eval(self.page, expression, return_by_value=True, await_promise=await_promise)

    def vm_eval(self, marker_method, body, await_promise=True):
        script = f"""
(async () => {{
  try {{
    const seen = new Set();
    const candidates = [];
    for (const el of Array.from(document.querySelectorAll('*'))) {{
      const v = el && el.__vue__;
      if (!v || seen.has(v)) continue;
      seen.add(v);
      const methods = Object.keys((v.$options && v.$options.methods) || {{}});
      if (!methods.includes({json.dumps(marker_method)})) continue;
      const style = window.getComputedStyle(el);
      const visible = style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0' && el.getClientRects().length > 0;
      if (!visible) continue;
      candidates.push({{
        vm: v,
        score: (el.innerText || '').length
      }});
    }}
    let vm = null;
    if (candidates.length) {{
      candidates.sort((a, b) => b.score - a.score);
      vm = candidates[0].vm;
    }} else {{
      const seen2 = new Set();
      for (const el of Array.from(document.querySelectorAll('*'))) {{
        const v = el && el.__vue__;
        if (!v || seen2.has(v)) continue;
        seen2.add(v);
        const methods = Object.keys((v.$options && v.$options.methods) || {{}});
        if (methods.includes({json.dumps(marker_method)})) {{
          vm = v;
          break;
        }}
      }}
    }}
    if (!vm) return {{ __error: 'vm not found', href: location.href, marker: {json.dumps(marker_method)} }};
    {body}
  }} catch (error) {{
    return {{ __error: String((error && error.stack) || error) }};
  }}
}})()
"""
        result = self.eval(script, await_promise=await_promise)
        if isinstance(result, dict) and result.get("__error"):
            raise RuntimeError(result["__error"])
        return result


def fetch_department_data(runner):
    runner.navigate("department")
    return runner.vm_eval(
        "fnNetRelateItems",
        """
await vm.fnNetRRelationList();
await vm.fnNetRList();
return {
  relation: vm.aRelationList,
  master: vm.aAllList || vm.aList
};
""",
    )


def save_department_mappings(runner, payload):
    return runner.vm_eval(
        "fnNetRelateItems",
        f"""
vm.aRelateItems = {json.dumps(payload, ensure_ascii=False)};
await vm.fnNetRelateItems();
await vm.fnNetRRelationList();
return vm.aRelationList;
""",
    )


def fetch_project_data(runner):
    runner.navigate("project")
    return runner.vm_eval(
        "fnNetRelateItems",
        """
await vm.fnNetRRelationList();
await vm.fnNetRList();
return {
  relation: vm.aRelationList,
  master: vm.aAllList || vm.aList
};
""",
    )


def save_project_mappings(runner, payload):
    return runner.vm_eval(
        "fnNetRelateItems",
        f"""
vm.aRelateItems = {json.dumps(payload, ensure_ascii=False)};
await vm.fnNetRelateItems();
await vm.fnNetRRelationList();
return vm.aRelationList;
""",
    )


def fetch_staff_data(runner):
    runner.navigate("staff")
    return runner.vm_eval(
        "fnNetRelateItems",
        """
await vm.fnNetRRelationList();
await vm.fnNetRList();
return {
  relation: vm.aRelationList,
  master: vm.aAllList || vm.aList
};
""",
    )


def save_staff_mappings(runner, payload):
    return runner.vm_eval(
        "fnNetRelateItems",
        f"""
vm.aRelateItems = {json.dumps(payload, ensure_ascii=False)};
await vm.fnNetRelateItems();
await vm.fnNetRRelationList();
return vm.aRelationList;
""",
    )


def fetch_provider_data(runner):
    runner.navigate("provider")
    return runner.vm_eval(
        "fnSaveCustomerRelation",
        """
vm.cur = 'relation';
await vm.fnNetRRelationList();
await vm.fnNetRList();
const bankRelation = vm.aRelationList;
vm.cur = 'receivePayAccount';
await vm.fnNetRRelationList();
const payRelation = vm.aRelationList;
await vm.fnNetCustomerRelationList();
return {
  bankRelation,
  payRelation,
  customerRelation: vm.cRelationList,
  providerMaster: vm.providerAllList,
  customerMaster: vm.customerAllList
};
""",
    )


def save_provider_bank_mappings(runner, payload, receive_type):
    cur = "relation" if receive_type == "BANKCARD" else "receivePayAccount"
    return runner.vm_eval(
        "fnSaveCustomerRelation",
        f"""
vm.cur = {json.dumps(cur)};
vm.aRelateItems = {json.dumps(payload, ensure_ascii=False)};
await vm.fnNetRelateItems();
await vm.fnNetRRelationList();
return vm.aRelationList;
""",
    )


def save_provider_customer_rows(runner, rows):
    return runner.vm_eval(
        "fnSaveCustomerRelation",
        f"""
const rows = {json.dumps(rows, ensure_ascii=False)};
for (const row of rows) {{
  await vm.fnSaveCustomerRelation(row);
}}
await vm.fnNetCustomerRelationList();
return vm.cRelationList;
""",
    )


def fetch_subject_data(runner):
    runner.navigate("subject")
    return runner.vm_eval(
        "fnNetSavePayRelateItems",
        """
await vm.fnNetPayRelationList(1);
await vm.fnNetIncomeRelationList(1);
await vm.fnSyncAllSubject();

async function loadPay(nodes, path = [], out = []) {
  for (const row of nodes || []) {
    const nextPath = path.concat([row.feeTemplateName]);
    out.push({ path: nextPath, row });
    if (row.hasChildren) {
      const kids = await vm.loadPayFeeRelation(row.feeTemplateId);
      for (const item of kids) item.hasChildren = item.parentFlag === '1';
      await loadPay(kids, nextPath, out);
    }
  }
  return out;
}

async function loadIncome(nodes, path = [], out = []) {
  for (const row of nodes || []) {
    const nextPath = path.concat([row.feeTemplateName]);
    out.push({ path: nextPath, row });
    if (row.hasChildren) {
      const kids = await vm.loadIncomeFeeRelation(row.feeTemplateId);
      for (const item of kids) item.hasChildren = !!item.parentFlag;
      await loadIncome(kids, nextPath, out);
    }
  }
  return out;
}

function walkSubjects(nodes, path = [], out = []) {
  for (const node of nodes || []) {
    const nextPath = path.concat([node.subjectName]);
    out.push({
      path: nextPath,
      subject: {
        id: node.id,
        subjectName: node.subjectName,
        subjectCode: node.subjectCode,
        subjectFullName: node.subjectFullName
      }
    });
    walkSubjects(node.children || [], nextPath, out);
  }
  return out;
}

const subjectResp = await vm.$dc.erp.fnNetQueryAllSubjectTree({ accountingId: vm.accountingId });
const subjectTree = (subjectResp && subjectResp.result) || [];

return {
  pay: await loadPay(vm.payRelationList || []),
  income: await loadIncome(vm.incomeRelationList || []),
  subjects: walkSubjects(subjectTree)
};
""",
    )


def save_subject_mappings(runner, pay_rows, income_rows):
    return runner.vm_eval(
        "fnNetSavePayRelateItems",
        f"""
const payRows = {json.dumps(pay_rows, ensure_ascii=False)};
const incomeRows = {json.dumps(income_rows, ensure_ascii=False)};
vm.payRelateItems = {{}};
vm.incomeRelateItems = {{}};
for (const row of payRows) vm.payRelateItems[row.feeTemplateId] = row;
for (const row of incomeRows) vm.incomeRelateItems[row.feeTemplateId] = row;
if (payRows.length) await vm.fnNetSavePayRelateItems();
if (incomeRows.length) await vm.fnNetSaveIncomeRelateItems();
await vm.fnNetPayRelationList(1);
await vm.fnNetIncomeRelationList(1);
return {{
  pay: vm.payRelationList,
  income: vm.incomeRelationList
}};
""",
    )


def build_department_payload(data):
    master_index = unique_index(data["master"], lambda item: normalize_text(item.get("deptName")))
    payload = []
    skipped = []
    for row in data["relation"]:
        ec = row["eccloudData"]
        current_id = (row.get("financialData") or {}).get("id")
        candidate, reason = choose_parallel_exact_candidate(ec.get("name"), ec.get("fullPathName"), master_index)
        if candidate is None:
            if current_id is not None:
                payload.append(
                    {
                        "eccloudId": ec["id"],
                        "financialId": None,
                        "accountingId": data["master"][0]["accountingId"] if data["master"] else None,
                        "_reason": f"clear_{reason}",
                        "_eccloudName": ec.get("fullPathName") or ec.get("name"),
                        "_financialName": None,
                    }
                )
            skipped.append({"name": ec.get("fullPathName") or ec.get("name"), "reason": reason})
            continue
        if current_id == candidate["id"]:
            continue
        payload.append(
            {
                "eccloudId": ec["id"],
                "financialId": candidate["id"],
                "accountingId": candidate["accountingId"],
                "_reason": reason,
                "_eccloudName": ec.get("fullPathName") or ec.get("name"),
                "_financialName": candidate.get("deptName"),
            }
        )
    return payload, skipped


def build_project_payload(data):
    master_index = unique_index(data["master"], lambda item: normalize_text(item.get("projectName")))
    payload = []
    skipped = []
    for row in data["relation"]:
        ec = row["eccloudData"]
        current_id = (row.get("financialData") or {}).get("id")
        candidate, reason = choose_parallel_exact_candidate(ec.get("name"), ec.get("fullPathName"), master_index)
        if candidate is None:
            if current_id is not None:
                payload.append(
                    {
                        "eccloudId": ec["id"],
                        "financialId": None,
                        "accountingId": data["master"][0]["accountingId"] if data["master"] else None,
                        "_eccloudName": ec.get("fullPathName") or ec.get("name"),
                        "_financialName": None,
                        "_reason": f"clear_{reason}",
                    }
                )
            skipped.append({"name": ec.get("fullPathName") or ec.get("name"), "reason": reason})
            continue
        if current_id == candidate["id"]:
            continue
        payload.append(
            {
                "eccloudId": ec["id"],
                "financialId": candidate["id"],
                "accountingId": candidate["accountingId"],
                "_eccloudName": ec.get("fullPathName") or ec.get("name"),
                "_financialName": candidate.get("projectName"),
            }
        )
    return payload, skipped


def build_staff_payload(data):
    master_index = unique_index(data["master"], lambda item: normalize_text(item.get("userName")))
    payload = []
    skipped = []
    for row in data["relation"]:
        ec = row["eccloudData"]
        current_id = (row.get("financialData") or {}).get("id")
        candidate = master_index.get(normalize_text(ec.get("name")))
        if candidate is None:
            if current_id is not None:
                payload.append(
                    {
                        "eccloudId": ec["id"],
                        "financialId": 0,
                        "accountingId": data["master"][0]["accountingId"] if data["master"] else None,
                        "_eccloudName": ec.get("name"),
                        "_financialName": None,
                        "_reason": "clear_no_match",
                    }
                )
            skipped.append({"name": ec.get("name"), "reason": "no_match"})
            continue
        if current_id == candidate["id"]:
            continue
        payload.append(
            {
                "eccloudId": ec["id"],
                "financialId": candidate["id"],
                "accountingId": candidate["accountingId"],
                "_eccloudName": ec.get("name"),
                "_financialName": candidate.get("userName"),
            }
        )
    return payload, skipped


def build_provider_payloads(data):
    provider_index = unique_index(
        [item for item in data["providerMaster"] if item.get("providerType") == "PROVIDER"],
        lambda item: normalize_text(item.get("providerName")),
    )
    customer_index = unique_index(data["customerMaster"], lambda item: normalize_text(item.get("providerName")))

    bank_payload = []
    bank_skipped = []
    for row in data["bankRelation"]:
        ec = row["eccloudData"]
        candidate = provider_index.get(normalize_text(ec.get("name")))
        if candidate is None:
            bank_skipped.append({"name": ec.get("name"), "reason": "no_match"})
            continue
        current_id = (row.get("financialData") or {}).get("id")
        if current_id == candidate["id"]:
            continue
        bank_payload.append(
            {
                "eccloudId": ec["id"],
                "financialId": candidate["id"],
                "providerType": candidate["providerType"],
                "accountingId": candidate["accountingId"],
                "_eccloudName": ec.get("name"),
                "_financialName": candidate.get("providerName"),
            }
        )

    pay_payload = []
    pay_skipped = []
    for row in data["payRelation"]:
        ec = row["eccloudData"]
        candidate = provider_index.get(normalize_text(ec.get("name")))
        if candidate is None:
            pay_skipped.append({"name": ec.get("name"), "reason": "no_match"})
            continue
        current_id = (row.get("financialData") or {}).get("id")
        if current_id == candidate["id"]:
            continue
        pay_payload.append(
            {
                "eccloudId": ec["id"],
                "financialId": candidate["id"],
                "providerType": candidate["providerType"],
                "accountingId": candidate["accountingId"],
                "_eccloudName": ec.get("name"),
                "_financialName": candidate.get("providerName"),
            }
        )

    customer_rows = []
    customer_skipped = []
    for row in data["customerRelation"]:
        candidate = customer_index.get(normalize_text(row.get("customerName")))
        current_id = row.get("financaProviderId")
        if candidate is None:
            if current_id is not None:
                updated = dict(row)
                updated["financaProviderId"] = None
                updated["financaProviderName"] = None
                customer_rows.append(updated)
            customer_skipped.append({"name": row.get("customerName"), "reason": "no_match"})
            continue
        if current_id == candidate["id"]:
            continue
        updated = dict(row)
        updated["financaProviderId"] = candidate["id"]
        updated["financaProviderName"] = candidate["providerName"]
        customer_rows.append(updated)

    return {
        "bank_payload": bank_payload,
        "bank_skipped": bank_skipped,
        "pay_payload": pay_payload,
        "pay_skipped": pay_skipped,
        "customer_rows": customer_rows,
        "customer_skipped": customer_skipped,
    }


def build_subject_payloads(data):
    subject_index = unique_index(
        data["subjects"],
        lambda item: tuple(normalize_text(part) for part in item["path"]),
    )

    def find_best_subject(path):
        normalized_path = [normalize_text(part) for part in path]
        matches = []
        for start in range(len(normalized_path)):
            key = tuple(normalized_path[start:])
            candidate = subject_index.get(key)
            if candidate is not None:
                matches.append((len(key), candidate))
        if not matches:
            return None
        max_len = max(length for length, _ in matches)
        best = [candidate for length, candidate in matches if length == max_len]
        if len(best) != 1:
            return None
        return best[0]

    def update_rows(rows, current_name_key, current_id_key, target_id_key, target_name_key):
        payload = []
        skipped = []
        for item in sorted(rows, key=lambda row: len(row["path"]), reverse=True):
            candidate = find_best_subject(item["path"])
            if candidate is None:
                skipped.append({"path": item["path"], "reason": "no_match"})
                continue
            row = dict(item["row"])
            if row.get(current_id_key) == candidate["subject"]["id"]:
                continue
            row[target_id_key] = candidate["subject"]["id"]
            row[target_name_key] = candidate["subject"]["subjectName"]
            payload.append(row)
        return payload, skipped

    pay_payload, pay_skipped = update_rows(
        data["pay"], "debitSubjectName", "debitSubjectId", "debitSubjectId", "debitSubjectName"
    )
    income_payload, income_skipped = update_rows(
        data["income"], "creditSubjectName", "creditSubjectId", "creditSubjectId", "creditSubjectName"
    )
    return {
        "pay_payload": pay_payload,
        "pay_skipped": pay_skipped,
        "income_payload": income_payload,
        "income_skipped": income_skipped,
    }


def strip_meta(items):
    return [{k: v for k, v in item.items() if not k.startswith("_")} for item in items]


def summarize_rows(rows, name_key):
    return [row.get(name_key) for row in rows]


def run(apply_changes=False, browser_name="edge", report_path=None):
    runner = CSTBrowserRunner(browser_name=browser_name)
    report = {"applied": apply_changes, "steps": []}

    subject_data = fetch_subject_data(runner)
    subject_plan = build_subject_payloads(subject_data)
    subject_step = {
        "step": "subject",
        "pay_apply_count": len(subject_plan["pay_payload"]),
        "pay_skip_count": len(subject_plan["pay_skipped"]),
        "income_apply_count": len(subject_plan["income_payload"]),
        "income_skip_count": len(subject_plan["income_skipped"]),
        "pay_paths": [item["path"] for item in subject_plan["pay_skipped"]],
        "income_paths": [item["path"] for item in subject_plan["income_skipped"]],
    }
    if apply_changes and (subject_plan["pay_payload"] or subject_plan["income_payload"]):
        save_subject_mappings(runner, subject_plan["pay_payload"], subject_plan["income_payload"])
        subject_step["saved"] = True
    report["steps"].append(subject_step)

    provider_data = fetch_provider_data(runner)
    provider_plan = build_provider_payloads(provider_data)
    provider_step = {
        "step": "provider",
        "bank_apply_count": len(provider_plan["bank_payload"]),
        "bank_skip_count": len(provider_plan["bank_skipped"]),
        "pay_apply_count": len(provider_plan["pay_payload"]),
        "pay_skip_count": len(provider_plan["pay_skipped"]),
        "customer_apply_count": len(provider_plan["customer_rows"]),
        "customer_skip_count": len(provider_plan["customer_skipped"]),
        "customer_skipped": provider_plan["customer_skipped"],
    }
    if apply_changes and provider_plan["bank_payload"]:
        save_provider_bank_mappings(runner, strip_meta(provider_plan["bank_payload"]), "BANKCARD")
        provider_step["bank_saved"] = True
    if apply_changes and provider_plan["pay_payload"]:
        save_provider_bank_mappings(runner, strip_meta(provider_plan["pay_payload"]), "PAYACCOUNT")
        provider_step["pay_saved"] = True
    if apply_changes and provider_plan["customer_rows"]:
        save_provider_customer_rows(runner, provider_plan["customer_rows"])
        provider_step["customer_saved"] = True
    report["steps"].append(provider_step)

    staff_data = fetch_staff_data(runner)
    staff_payload, staff_skipped = build_staff_payload(staff_data)
    staff_step = {
        "step": "staff",
        "apply_count": len(staff_payload),
        "skip_count": len(staff_skipped),
        "skipped": staff_skipped,
    }
    if apply_changes and staff_payload:
        save_staff_mappings(runner, strip_meta(staff_payload))
        staff_step["saved"] = True
    report["steps"].append(staff_step)

    project_data = fetch_project_data(runner)
    project_payload, project_skipped = build_project_payload(project_data)
    project_step = {
        "step": "project",
        "apply_count": len(project_payload),
        "skip_count": len(project_skipped),
        "skipped": project_skipped,
    }
    if apply_changes and project_payload:
        save_project_mappings(runner, strip_meta(project_payload))
        project_step["saved"] = True
    report["steps"].append(project_step)

    department_data = fetch_department_data(runner)
    department_payload, department_skipped = build_department_payload(department_data)
    department_step = {
        "step": "department",
        "apply_count": len(department_payload),
        "skip_count": len(department_skipped),
        "skipped": department_skipped,
    }
    if apply_changes and department_payload:
        save_department_mappings(runner, strip_meta(department_payload))
        department_step["saved"] = True
    report["steps"].append(department_step)

    if report_path:
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description="Configure 财税通 ERP archive mappings from the current Edge session.")
    default_report = Path(__file__).resolve().parent.parent / "cst_live_mapper_report.json"
    parser.add_argument("--apply", action="store_true", help="actually save mappings")
    parser.add_argument("--browser", default="edge", help="browser to attach to")
    parser.add_argument(
        "--report",
        default=str(default_report),
        help="where to write the JSON summary",
    )
    args = parser.parse_args()

    report = run(apply_changes=args.apply, browser_name=args.browser, report_path=args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
