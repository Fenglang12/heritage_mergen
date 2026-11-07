"""临时脚本：测试 .env 中智谱 Key 与各模型额度（测完可删）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from core.config import Config

CHAT_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
GEN_URL = "https://open.bigmodel.cn/api/paas/v4/images/generations"


def main():
    key = Config.ZHIPU_API_KEY
    print("KEY loaded:", bool(key), "prefix:", (key[:8] + "...") if key else "EMPTY")
    print("VISION:", Config.ZHIPU_VISION_MODEL)
    print("IMAGE:", Config.ZHIPU_IMAGE_MODEL)
    if not key:
        return 1

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    body = {
        "model": Config.ZHIPU_VISION_MODEL,
        "messages": [{"role": "user", "content": "只回复OK"}],
        "max_tokens": 10,
    }
    r = requests.post(CHAT_URL, json=body, headers=headers, timeout=30)
    print("\n--- GLM chat ---", r.status_code)
    print(r.text[:600])

    candidates = [
        Config.ZHIPU_IMAGE_MODEL,
        "cogview-3-flash",
        "cogview-4",
        "glm-image",
    ]
    seen = set()
    for model in candidates:
        if model in seen:
            continue
        seen.add(model)
        body2 = {
            "model": model,
            "prompt": "非遗剪纸红色对称图案，简洁",
            "size": "1024x1024",
        }
        r2 = requests.post(GEN_URL, json=body2, headers=headers, timeout=120)
        try:
            j = r2.json()
            err = (j.get("error") or {}).get("message") or j.get("message") or ""
            ok = r2.status_code == 200 and j.get("data")
        except Exception as exc:
            err = str(exc)
            ok = False
            j = {}
        print(f"\n--- IMAGE {model} --- status={r2.status_code} ok={ok}")
        if err:
            print("err:", err[:200])
        if ok:
            url = (j.get("data") or [{}])[0].get("url", "")
            print("url:", url[:100])
            print("\nRECOMMEND_IMAGE_MODEL=", model)
            return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
