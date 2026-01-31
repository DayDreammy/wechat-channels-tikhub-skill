# TikHub WeChat Channels API quick reference

## Endpoints (WeChat Channels)

Base: `https://api.tikhub.io`

- `GET /api/v1/wechat_channels/fetch_user_search`
  - Params: `keywords`, `page` (start from 1)
  - Purpose: search users by keyword

- `GET /api/v1/wechat_channels/fetch_home_page`
  - Params: `username`, `last_buffer` (optional for pagination)
  - Purpose: fetch user profile + video list
  - Video list is in `data.object` or `data.object_list`

- `GET /api/v1/wechat_channels/fetch_video_detail`
  - Params: `id` or `exportId`
  - Purpose: fetch single video detail

## Media fields

From `object_desc.media[0]`:

- `url` and `url_token`: concatenate for a download URL
- `decode_key`: per-request key for decryption (changes every request)

Important:
- Always download and decrypt using `url`/`url_token` + `decode_key` from the SAME response.
- If MP4 is not playable, use `decode_key` with the decrypt tool.

## Decrypt API (Evil0ctal)

Recommended local API service:

```bash
docker run -d -p 3005:3000 --name wechat-decrypt-api evil0ctal/wechat-decrypt-api:latest
```

Keystream endpoint:

```bash
curl -X POST http://localhost:3005/api/keystream \
  -H 'Content-Type: application/json' \
  -d '{"decode_key": "<decode_key>"}'
```

Use the keystream (hex) to XOR-decrypt the first 131072 bytes of the encrypted file.

Full decrypt (optional):

```bash
curl -X POST http://localhost:3005/api/decrypt \
  -F "video=@encrypted.mp4" \
  -F "decode_key=<decode_key>" \
  -o decrypted.mp4
```
