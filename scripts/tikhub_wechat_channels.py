#!/usr/bin/env python3
"""TikHub WeChat Channels pipeline.

- Search user by keyword (optional)
- Fetch user home page (video list)
- Download latest video
- Decrypt using local decrypt API keystream endpoint
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

API_BASE = "https://api.tikhub.io"


def _api_get(api_key: str, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{API_BASE}{path}"
    resp = requests.get(url, params=params, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} {resp.text[:500]}")
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"API error: {data}")
    return data


def _select_user(data: List[Dict[str, Any]], index: int) -> Dict[str, Any]:
    if not data:
        raise RuntimeError("No users found")
    if index < 0 or index >= len(data):
        raise RuntimeError(f"User index out of range: {index}")
    return data[index]


def _get_object_list(home_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    if "object_list" in home_data:
        return home_data["object_list"]
    if "object" in home_data:
        return home_data["object"]
    return []


def _human_time(ts: Optional[int]) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _download_file(url: str, out_path: Path) -> None:
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with out_path.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def _fetch_keystream(decrypt_api: str, decode_key: str) -> bytes:
    resp = requests.post(f"{decrypt_api.rstrip('/')}/api/keystream", json={"decode_key": str(decode_key)}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    keystream_hex = data.get("keystream")
    if not keystream_hex:
        raise RuntimeError(f"No keystream in response: {data}")
    return bytes.fromhex(keystream_hex)


def _decrypt_file(enc_path: Path, out_path: Path, keystream: bytes) -> None:
    with enc_path.open("rb") as fin, out_path.open("wb") as fout:
        head = fin.read(len(keystream))
        if not head:
            raise RuntimeError("Encrypted file is empty")
        dec_head = bytes(a ^ b for a, b in zip(head, keystream))
        fout.write(dec_head)
        while True:
            buf = fin.read(1024 * 1024)
            if not buf:
                break
            fout.write(buf)


def main() -> None:
    parser = argparse.ArgumentParser(description="TikHub WeChat Channels pipeline")
    parser.add_argument("--api-key", required=True, help="TikHub API key")
    parser.add_argument("--keyword", help="User search keyword (e.g. 李大霄)")
    parser.add_argument("--page", type=int, default=1, help="Search page (default: 1)")
    parser.add_argument("--user-index", type=int, default=0, help="Index in search results to use (default: 0)")
    parser.add_argument("--username", help="WeChat Channels username (skips search if provided)")
    parser.add_argument("--outdir", default="output", help="Output directory")
    parser.add_argument("--decrypt-api", default="http://localhost:3005", help="Decrypt API base URL")
    parser.add_argument("--skip-decrypt", action="store_true", help="Skip decryption step")
    parser.add_argument("--skip-download", action="store_true", help="Skip download if encrypted file exists")

    args = parser.parse_args()

    if not args.username and not args.keyword:
        parser.error("Provide --username or --keyword")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    username = args.username
    if not username:
        res = _api_get(args.api_key, "/api/v1/wechat_channels/fetch_user_search", {
            "keywords": args.keyword,
            "page": args.page,
        })
        data = res.get("data", [])
        print(f"Search results: {len(data)}")
        for i, item in enumerate(data[:10]):
            contact = item.get("contact", {})
            nickname = contact.get("nickname")
            uname = contact.get("username")
            signature = (contact.get("signature") or "").replace("\n", " ")[:60]
            print(f"[{i}] {nickname} | {uname} | {signature}")
        user = _select_user(data, args.user_index)
        username = user.get("contact", {}).get("username")
        if not username:
            raise RuntimeError("Selected user has no username")
        print(f"Selected username: {username}")

    home = _api_get(args.api_key, "/api/v1/wechat_channels/fetch_home_page", {"username": username})
    home_data = home.get("data", {})
    videos = _get_object_list(home_data)
    print(f"Videos fetched: {len(videos)}")
    if not videos:
        raise RuntimeError("No videos found in home page response")

    # Sort by createtime to find latest
    latest = max(videos, key=lambda x: x.get("createtime") or 0)
    latest_id = latest.get("id")
    desc = (latest.get("object_desc", {}).get("description") or "").replace("\n", " ")
    createtime = latest.get("createtime")
    media = (latest.get("object_desc", {}) or {}).get("media", [])
    if not media:
        raise RuntimeError("Latest video has no media")
    url = media[0].get("url")
    url_token = media[0].get("url_token") or ""
    decode_key = media[0].get("decode_key")
    if not url or not decode_key:
        raise RuntimeError("Missing url or decode_key in latest media")
    full_url = url + url_token

    enc_path = outdir / f"{latest_id}_encrypted.mp4"
    dec_path = outdir / f"{latest_id}_decrypted.mp4"
    meta_path = outdir / f"{latest_id}_meta.json"

    print("Latest video:")
    print(f"  id: {latest_id}")
    print(f"  desc: {desc}")
    print(f"  createtime: {createtime} ({_human_time(createtime)})")
    print(f"  decode_key: {decode_key}")

    if args.skip_download:
        if not enc_path.exists():
            raise RuntimeError(f"Encrypted file not found: {enc_path}")
        print(f"Skip download, using existing file: {enc_path}")
    else:
        print(f"Downloading to {enc_path}...")
        _download_file(full_url, enc_path)
        print(f"Downloaded {enc_path} ({enc_path.stat().st_size} bytes)")

    meta = {
        "username": username,
        "latest_id": latest_id,
        "description": desc,
        "createtime": createtime,
        "createtime_utc": _human_time(createtime),
        "decode_key": decode_key,
        "url": url,
        "url_token": url_token,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved metadata: {meta_path}")

    if args.skip_decrypt:
        print("Skip decrypt step")
        return

    print(f"Requesting keystream from {args.decrypt_api}...")
    keystream = _fetch_keystream(args.decrypt_api, str(decode_key))
    print(f"Keystream length: {len(keystream)} bytes")

    print(f"Decrypting to {dec_path}...")
    _decrypt_file(enc_path, dec_path, keystream)
    print(f"Decrypted file: {dec_path} ({dec_path.stat().st_size} bytes)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
