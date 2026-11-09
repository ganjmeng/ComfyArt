# 本地复核供应商设置

这是设置面板加真实的 `/comfyart/provider-admin` 接口。用户目录是进程自己的临时文件夹。不会调用生成供应商，也不要填真实密钥。

1. 在仓库根目录构建预览：

```bash
npx vite build --config tests/js/provider-admin/vite.config.ts --outDir /tmp/provider-ui --emptyOutDir
```

2. 起两套接口。密钥只用任意非空占位，不要用真实令牌。例如本地字符串 `local-test-token` 和 `local-test-llm`。

```bash
PORT=8765 REPLICATE_API_TOKEN=local-test-token DEEPSEEK_API_KEY=local-test-llm \
  PROVIDER_UI_DIST=/tmp/provider-ui python3 tests/js/provider-admin/live_server.py
```

另一个终端不要设置这两个变量：

```bash
PORT=8766 PROVIDER_UI_DIST=/tmp/provider-ui python3 tests/js/provider-admin/live_server.py
```

3. 浏览器打开 `http://127.0.0.1:8765/`，点「供应商」。缺密钥用 `http://127.0.0.1:8766/`。

4. 自动走查：

```bash
python3 tests/js/provider-admin/walk.py
```

带 `?mock=1` 的预览仍会拦截请求，只能看界面，不能当成这条走查。
