# 控制页图集管理

用户已确认：在现有控制页增加图集入口，支持查看、新建、切换、缩略图和原图、上传、来源和保存时间、删除单张图片及空图集；删除前确认。沿用已确认架构、认证和现有页面风格，不新增依赖或部署。

- [x] `albums.py` 增加删除单图及空图集，`album_api.py` 增加对应 DELETE 路由。空图集用 rmdir 删除，非空返回 409；图和同名 JSON 一起删除，不递归删除目录。
- [x] 现有页面增加“图集管理”标签，`albums.js` 处理页面交互，复用 admin.js 请求方法。列表为缩略图、来源、日期和删除操作；点击原图在新标签打开；上传沿用单图二进制接口。
- [x] 扩展已有图集 API 测试，验证认证、删除后不可读取/随机抽到、非空图集不能删除及不同图集不受影响。不增加永久 UI 测试。
- [x] 更新文档，运行 pytest、JS 语法、diff 检查；可用时仅截图检查页面，不自动点击、填表或测试真实业务交互。

## 验证记录

- `.venv/bin/pytest -q`：沙箱内 TestClient 启动等待，定向超时诊断表明停在既有 fixture 的 portal 启动；终止该次运行。沙箱外相同命令 53 passed，2 条既有依赖弃用警告。
- `node --check qqbot/static/admin.js`、`node --check qqbot/static/forms.js`、`node --check qqbot/static/albums.js`：通过。
- `git diff --check`：通过。
- 本地截图使用真实页面脚本、临时 AlbumStore 测试图片和只读 GET fixture：1440px 桌面及 390px 手机均无横向溢出、无脚本错误；未执行自动点击、填表、上传或删除。
- 截图路径 `/tmp/sunyunbo/qqbot-album-admin-20261025/{desktop,mobile}.png`。未部署、未操作真实图片数据。
