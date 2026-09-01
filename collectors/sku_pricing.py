import json
from pathlib import Path


def load_pricing(path):
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def get_sku_price(sku_id, pricing):
    return float(pricing.get("skus", {}).get(sku_id, {}).get("price", 0.0))


def get_sku_name(sku_id, pricing):
    return pricing.get("skus", {}).get(sku_id, {}).get("name", sku_id)


def calculate_user_monthly_cost(licenses, pricing):
    return round(sum(get_sku_price(sku_id, pricing) for sku_id in licenses), 2)


def calculate_savings(recommendations, pricing):
    by_flag = {}
    for recommendation in recommendations:
        cost = calculate_user_monthly_cost(recommendation.get("licenses", []), pricing)
        counted = set()
        for flag in recommendation.get("flags", []):
            confidence = str(flag.get("confidence", "")).lower()
            flag_name = flag.get("flag")
            if confidence not in ("high", "medium") or flag_name in counted:
                continue
            counted.add(flag_name)
            entry = by_flag.setdefault(flag_name, {"users": 0, "monthly": 0.0})
            entry["users"] += 1
            entry["monthly"] = round(entry["monthly"] + cost, 2)
    total_monthly = round(sum(item["monthly"] for item in by_flag.values()), 2)
    return {"total_monthly_saving": total_monthly, "total_annual_saving": round(total_monthly * 12, 2), "by_flag": by_flag, "currency": pricing.get("currency", "USD")}
