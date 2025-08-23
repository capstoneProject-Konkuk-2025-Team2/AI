# import os, json, re, time
# from pathlib import Path
# from statistics import mean
# import numpy as np  # nDCG 계산용

# from app.chatbot.agent_rag_chatbot import (
#     initialize_activities,
#     ranked_programs,
#     resolve_followup_question,
#     answer_program_question_by_title,
# )
# from app.services.user_service import load_user_profile


# # ------------ Retrieval metrics ------------
# def hit_at_k_exact(expected_titles, got_rows):
#     got_titles = [r["title"] for r in got_rows]
#     return 1 if any(any(exp == got for got in got_titles) for exp in expected_titles) else 0

# def hit_at_k_regex(expected_titles_regex, got_rows):
#     got_titles = [r["title"] for r in got_rows]
#     for pat in expected_titles_regex:
#         cre = re.compile(pat)
#         if any(cre.search(t or "") for t in got_titles):
#             return 1
#     return 0

# def reciprocal_rank(expected_regex_list, got_rows):
#     # 첫 일치 랭크의 역수
#     for i, r in enumerate(got_rows, start=1):
#         if any(re.search(p, r["title"] or "") for p in expected_regex_list):
#             return 1.0 / i
#     return 0.0

# def ndcg_at_k(expected_regex_list, got_rows, k=5):
#     rels = [1 if any(re.search(p, r["title"] or "") for p in expected_regex_list) else 0 for r in got_rows[:k]]
#     def dcg(xs):
#         return sum(x / (np.log2(i + 2)) for i, x in enumerate(xs))
#     ideal = sorted(rels, reverse=True)
#     return (dcg(rels) / dcg(ideal)) if sum(ideal) > 0 else 0.0

# def precision_recall_at_k(expected_regex_list, got_rows, k=5):
#     top = got_rows[:k]
#     hits = sum(1 for r in top if any(re.search(p, r["title"] or "") for p in expected_regex_list))
#     prec = hits / max(1, len(top))
#     rec  = hits / max(1, len(expected_regex_list))  # 근사치
#     return prec, rec


# # ------------ Retrieval runner ------------
# def mileage_all_equal(got_rows, expected_mileage):
#     if not got_rows:
#         print("[DEBUG][mileage] no rows returned")
#         return 0
#     bad = []
#     for r in got_rows:
#         v = r["fields"].get("KUM마일리지")
#         if not v or int(v) != int(expected_mileage):
#             bad.append((r["title"], v))
#     if bad:
#         print(f"[DEBUG][mileage_mismatch] expected={expected_mileage} got={bad[:5]}")
#         return 0
#     return 1

# def run_retrieval(sample, user_profile):
#     # ★ expected_mileage가 있으면 쿼리에 숫자 붙여 필터 강제 적용
#     query = sample["query"]
#     if "expected_mileage" in sample:
#         query = f'{query} KUM 마일리지 {sample["expected_mileage"]}점'

#     t0 = time.perf_counter()
#     rows = ranked_programs(query, user_profile, k=sample.get("k", 5))
#     latency = time.perf_counter() - t0

#     if "expected_titles" in sample:
#         score = hit_at_k_exact(sample["expected_titles"], rows)
#         metric_name = "hit@k_exact"
#     elif "expected_titles_regex" in sample:
#         score = hit_at_k_regex(sample["expected_titles_regex"], rows)
#         metric_name = "hit@k_regex"
#     elif "expected_mileage" in sample:
#         score = mileage_all_equal(rows, sample["expected_mileage"])
#         metric_name = "mileage_filter_ok"
#     else:
#         score = 0
#         metric_name = "n/a"

#     # 필요시 보조지표 계산 예시 (주석 해제해서 사용)
#     # extra = {}
#     # if "expected_titles_regex" in sample:
#     #     rr = reciprocal_rank(sample["expected_titles_regex"], rows)
#     #     ndcg = ndcg_at_k(sample["expected_titles_regex"], rows, k=sample.get("k", 5))
#     #     p, r = precision_recall_at_k(sample["expected_titles_regex"], rows, k=sample.get("k", 5))
#     #     extra.update({"RR": rr, "nDCG": ndcg, "P@k": p, "R@k": r})
#     # return {"type": "retrieval", "metric": metric_name, "score": score, "latency_s": latency, **extra}

#     return {"type": "retrieval", "metric": metric_name, "score": score, "latency_s": latency}


# # ------------ Field runner ------------
# def run_field(sample, user_profile):
#     # 컨텍스트 세팅(상위 추천 한 번 호출해서 last_queried_title 잡기)
#     from app.chatbot.agent_rag_chatbot import search_top5_programs_with_explanation
#     _ = search_top5_programs_with_explanation(sample["context_query"], user_profile)

#     t0 = time.perf_counter()
#     query = resolve_followup_question(sample["query_after"])
#     answer = answer_program_question_by_title(query)  # 규칙기반 단답 우선
#     latency = time.perf_counter() - t0

#     field = sample["field"]
#     ok = 1 if re.search(sample["expected_value_regex"], answer) else 0

#     return {
#         "type": "field",
#         "metric": f"{field}_exact_regex",
#         "score": ok,
#         "latency_s": latency,
#         "raw_answer": answer,
#     }


# # ------------ Main ------------
# def main():
#     initialize_activities()
#     golden_path = Path("app/eval/golden.jsonl")
#     assert golden_path.exists(), f"not found: {golden_path}"

#     results = []
#     with open(golden_path, "r", encoding="utf-8") as f:
#         for line in f:
#             if not line.strip():
#                 continue
#             sample = json.loads(line)
#             user_profile = load_user_profile(sample["user_id"])
#             assert user_profile, f"user {sample['user_id']} not found"

#             if sample["type"] == "retrieval":
#                 results.append(run_retrieval(sample, user_profile))
#             elif sample["type"] == "field":
#                 results.append(run_field(sample, user_profile))
#             else:
#                 continue

#     # 요약
#     by_metric = {}
#     for r in results:
#         key = (r["type"], r["metric"])
#         by_metric.setdefault(key, []).append(r)

#     print("=== RAG Eval Summary ===")
#     for (typ, metric), arr in by_metric.items():
#         acc = mean(x["score"] for x in arr) if arr else 0.0
#         lat = mean(x["latency_s"] for x in arr) if arr else 0.0
#         print(f"{typ:<10} | {metric:<16} | accuracy={acc:.2f} | avg_latency={lat*1000:.0f} ms")

#     print("\n--- Details ---")
#     for r in results:
#         print(r)


# if __name__ == "__main__":
#     main()
import os, json, re, time
from pathlib import Path
from statistics import mean
import numpy as np  # nDCG 계산용

from app.chatbot.agent_rag_chatbot import (
    initialize_activities,
    ranked_programs,
    resolve_followup_question,
    answer_program_question_by_title,
)
from app.services.user_service import load_user_profile


# ------------ Retrieval metrics ------------
def hit_at_k_exact(expected_titles, got_rows):
    got_titles = [r["title"] for r in got_rows]
    return 1 if any(any(exp == got for got in got_titles) for exp in expected_titles) else 0

def hit_at_k_regex(expected_titles_regex, got_rows):
    got_titles = [r["title"] for r in got_rows]
    for pat in expected_titles_regex:
        cre = re.compile(pat)
        if any(cre.search(t or "") for t in got_titles):
            return 1
    return 0

def reciprocal_rank(expected_regex_list, got_rows):
    # 첫 일치 랭크의 역수
    for i, r in enumerate(got_rows, start=1):
        if any(re.search(p, r["title"] or "") for p in expected_regex_list):
            return 1.0 / i
    return 0.0

def ndcg_at_k(expected_regex_list, got_rows, k=5):
    rels = [1 if any(re.search(p, r["title"] or "") for p in expected_regex_list) else 0 for r in got_rows[:k]]
    def dcg(xs):
        return sum(x / (np.log2(i + 2)) for i, x in enumerate(xs))
    ideal = sorted(rels, reverse=True)
    return (dcg(rels) / dcg(ideal)) if sum(ideal) > 0 else 0.0

def precision_recall_at_k(expected_regex_list, got_rows, k=5):
    top = got_rows[:k]
    hits = sum(1 for r in top if any(re.search(p, r["title"] or "") for p in expected_regex_list))
    prec = hits / max(1, len(top))
    rec  = hits / max(1, len(expected_regex_list))  # 근사치
    return prec, rec


# ------------ Retrieval runner ------------
def mileage_all_equal(got_rows, expected_mileage):
    if not got_rows:
        print("[DEBUG][mileage] no rows returned")
        return 0
    bad = []
    for r in got_rows:
        v = r["fields"].get("KUM마일리지")
        if not v or int(v) != int(expected_mileage):
            bad.append((r["title"], v))
    if bad:
        print(f"[DEBUG][mileage_mismatch] expected={expected_mileage} got={bad[:5]}")
        return 0
    return 1

def run_retrieval(sample, user_profile):
    # ★ expected_mileage가 있으면 쿼리에 숫자 붙여 필터 강제 적용
    query = sample["query"]
    if "expected_mileage" in sample:
        query = f'{query} KUM 마일리지 {sample["expected_mileage"]}점'

    t0 = time.perf_counter()
    rows = ranked_programs(query, user_profile, k=sample.get("k", 5))
    latency = time.perf_counter() - t0

    if "expected_titles" in sample:
        score = hit_at_k_exact(sample["expected_titles"], rows)
        metric_name = "hit@k_exact"
    elif "expected_titles_regex" in sample:
        score = hit_at_k_regex(sample["expected_titles_regex"], rows)
        metric_name = "hit@k_regex"
    elif "expected_mileage" in sample:
        score = mileage_all_equal(rows, sample["expected_mileage"])
        metric_name = "mileage_filter_ok"
    else:
        score = 0
        metric_name = "n/a"

    # rows를 함께 반환 -> main에서 보조지표 계산용으로만 사용(요약표엔 노출 안 함)
    return {"type": "retrieval", "metric": metric_name, "score": score, "latency_s": latency, "rows": rows}


# ------------ Field runner ------------
def run_field(sample, user_profile):
    # 컨텍스트 세팅(상위 추천 한 번 호출해서 last_queried_title 잡기)
    from app.chatbot.agent_rag_chatbot import search_top5_programs_with_explanation
    _ = search_top5_programs_with_explanation(sample["context_query"], user_profile)

    t0 = time.perf_counter()
    query = resolve_followup_question(sample["query_after"])
    answer = answer_program_question_by_title(query)  # 규칙기반 단답 우선
    latency = time.perf_counter() - t0

    field = sample["field"]
    ok = 1 if re.search(sample["expected_value_regex"], answer) else 0

    return {
        "type": "field",
        "metric": f"{field}_exact_regex",
        "score": ok,
        "latency_s": latency,
        "raw_answer": answer,
    }


# ------------ Main ------------
def main():
    initialize_activities()
    golden_path = Path("app/eval/golden.jsonl")
    assert golden_path.exists(), f"not found: {golden_path}"

    results = []
    with open(golden_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            sample = json.loads(line)
            user_profile = load_user_profile(sample["user_id"])
            assert user_profile, f"user {sample['user_id']} not found"

            if sample["type"] == "retrieval":
                r = run_retrieval(sample, user_profile)

                # 1) 기본 메트릭은 rows 제외하고 저장 (요약표가 깔끔하도록)
                results.append({k: v for k, v in r.items() if k != "rows"})

                # 2) 보조지표: expected_titles_regex가 있을 때만 계산
                if "expected_titles_regex" in sample:
                    rows = r.get("rows", [])
                    k = sample.get("k", 5)

                    # MRR@k
                    mrr = reciprocal_rank(sample["expected_titles_regex"], rows[:k])
                    results.append({
                        "type": "retrieval",
                        "metric": f"MRR@{k}",
                        "score": mrr,
                        "latency_s": float(r["latency_s"]),  # 포맷 통일용
                    })

                    # nDCG@k
                    nd = ndcg_at_k(sample["expected_titles_regex"], rows, k=k)
                    results.append({
                        "type": "retrieval",
                        "metric": f"nDCG@{k}",
                        "score": nd,
                        "latency_s": float(r["latency_s"]),
                    })

                    # Recall@1 (Top-1이 정답이면 1)
                    top1 = rows[:1]
                    rec1 = 1.0 if (top1 and any(re.search(p, top1[0]["title"] or "") 
                                                 for p in sample["expected_titles_regex"])) else 0.0
                    results.append({
                        "type": "retrieval",
                        "metric": "Recall@1",
                        "score": rec1,
                        "latency_s": float(r["latency_s"]),
                    })

                    # (옵션) Precision@k / Recall@k 근사치도 원하면 주석 해제
                    # prec, rec = precision_recall_at_k(sample["expected_titles_regex"], rows, k=k)
                    # results.append({"type":"retrieval","metric":f"Precision@{k}","score":prec,"latency_s":r["latency_s"]})
                    # results.append({"type":"retrieval","metric":f"Recall@{k}(approx)","score":rec,"latency_s":r["latency_s"]})

            elif sample["type"] == "field":
                results.append(run_field(sample, user_profile))
            else:
                continue

    # 요약
    by_metric = {}
    for r in results:
        key = (r["type"], r["metric"])
        by_metric.setdefault(key, []).append(r)

    print("=== RAG Eval Summary ===")
    for (typ, metric), arr in by_metric.items():
        acc = mean(x["score"] for x in arr) if arr else 0.0
        lat = mean(x["latency_s"] for x in arr) if arr else 0.0
        print(f"{typ:<10} | {metric:<16} | accuracy={acc:.2f} | avg_latency={lat*1000:.0f} ms")

    print("\n--- Details ---")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()