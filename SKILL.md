---
name: wechat-channels-tikhub
description: "TikHub WeChat Channels (视频号) API workflow: search users by keyword, fetch a user home page/video list, download the latest video, and decrypt it into a playable MP4 using decode_key + local decrypt API. Use when integrating or troubleshooting TikHub WeChat Channels endpoints or turning a username/keyword into a playable video file."
---

# WeChat Channels TikHub

## Overview

Run an end-to-end pipeline for WeChat Channels: search a user, fetch their video list, download the latest video, and decrypt it using the decode_key and a local decrypt API.

## Workflow (recommended)

1. **Confirm API key & balance**
   - Ensure the TikHub API key has paid access (WeChat Channels endpoints do not accept free credits).

2. **Start local decrypt API**
   - Use the Docker service (default port 3005 to avoid conflicts):

```bash
docker run -d -p 3005:3000 --name wechat-decrypt-api evil0ctal/wechat-decrypt-api:latest
```

3. **Run the pipeline script**

```bash
python /home/yy/.codex/skills/wechat-channels-tikhub/scripts/tikhub_wechat_channels.py \
  --api-key "<TIKHUB_API_KEY>" \
  --keyword "李大霄" \
  --outdir output \
  --decrypt-api http://localhost:3005
```

- If you already have the exact username, skip search:

```bash
python /home/yy/.codex/skills/wechat-channels-tikhub/scripts/tikhub_wechat_channels.py \
  --api-key "<TIKHUB_API_KEY>" \
  --username "<username>@finder" \
  --outdir output
```

## Outputs

- `output/<video_id>_encrypted.mp4`
- `output/<video_id>_decrypted.mp4`
- `output/<video_id>_meta.json`

## Media utilities

- Compress decrypted video to <=50MB:

```bash
python /home/yy/.codex/skills/wechat-channels-tikhub/scripts/compress_video_to_size.py \
  --input output/<video_id>_decrypted.mp4 \
  --target-mb 50
```

- Extract audio file:

```bash
python /home/yy/.codex/skills/wechat-channels-tikhub/scripts/extract_audio.py \
  --input output/<video_id>_decrypted.mp4 \
  --codec aac \
  --bitrate 128
```

## Troubleshooting

- **HTTP 402**: balance不足，微信视频号接口不接受免费额度。
- **HTTP 403**: API key lacks scopes. Enable permissions in TikHub dashboard.
- **500 / Tool errors**: usually a wrapped HTTP error; call the REST endpoint directly to inspect details.
- **Decrypt API errors**: check container logs with `docker logs wechat-decrypt-api`.

## References

- See `references/tikhub_wechat_channels.md` for endpoint details and decrypt notes.
