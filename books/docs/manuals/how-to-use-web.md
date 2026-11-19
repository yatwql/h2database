# Web 使用

Web 渠道提供单页控制台与 JSON API，适合演示或远程机器上操作。

```bash
books/scripts/launch.sh web                 # 默认 127.0.0.1:8080
books/scripts/launch.sh web --port 9000
books/scripts/launch.sh web --host 0.0.0.0  # 仅在你明确需要外部访问时
```

浏览器打开 `http://127.0.0.1:8080/` 即可看到按钮式控制台。

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 单页控制台（按钮对应 action） |
| GET | `/api/status` | `{"code":0,"output":"书籍/配置/LLM 状态"}` |
| POST | `/api/run` | 请求 `{"action":"check"}`，可选 `{"prompt":"…"}` 用于 `llm-ask` |

```bash
curl -s localhost:8080/api/status | python -m json.tool
curl -s -X POST localhost:8080/api/run \
     -H 'Content-Type: application/json' \
     -d '{"action":"build"}' | python -m json.tool
```

响应统一是 `{"code": <退出码>, "output": "<命令输出>"}`。

## 注意

- 默认只绑 `127.0.0.1`：这些动作会写仓库（手稿、产物、日志），不要随意暴露公网。
- 没有鉴权；如需远程使用，请放在反向代理与访问控制之后。
- 每个请求同步执行，长动作（deliver）可能持续数十秒，请调大客户端超时。
- 日志与 CLI/TUI 一致写入 `books/logs/`。
