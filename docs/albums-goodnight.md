# 图集与定时晚安

## 公共图集

图集由宿主提供，人工上传和插件写入使用同一份存储。每个图集有唯一 ID，允许 1 至 64 个英文字母、数字、下划线和短横线。不同插件和群可以共享同一个图集，也可以分别指定。

数据位于 `BOT_CONFIG_PATH` 同级的 `albums/<图集ID>/`，默认 `data/albums/`。每张原图对应一份同名 JSON，记录图片 ID、图集 ID、格式、大小、创建时间、来源和业务 `metadata`。图片由服务端分配文件名，保留原始字节，支持 JPEG、PNG、GIF、WebP、BMP、TIFF、AVIF；没有去重、自动清理或数据库。

## 管理 HTTP 接口

全部使用现有管理后台的 HTTP Basic 账号密码，不提供公开图片链接。写请求还须带 `X-Requested-With: qqbot-admin`。图集管理不依赖某个业务插件是否开启。

控制页新增“图集管理”标签：可新建和切换图集，上传单张图片，浏览缩略图、来源和保存时间，点击查看原图。图片监测写入的图片也出现在这里。删除图片或空图集前会提示确认；非空图集不能直接删除。删除图片会同时清理同名 JSON，后续随机取图不再包含该图片。删除图集不会修改插件配置，后续插件再次写入同名图集会自动创建。

| 方法和路径 | 请求与返回 |
| --- | --- |
| `GET /api/albums` | 返回 `[{"id":"goodnight"}]` |
| `POST /api/albums` | 请求 `{"id":"goodnight"}`，返回图集 ID；重复创建沿用已有图集 |
| `POST /api/albums/{album}/images` | 原始图片二进制请求体，最大 10 MiB；成功返回 201 和图片记录，附 `url` |
| `GET /api/albums/{album}/images` | 返回图片记录列表，附每张原图的 `url` |
| `GET /api/albums/{album}/images/{image_id}` | 返回原图，仍需后台登录 |
| `DELETE /api/albums/{album}/images/{image_id}` | 删除指定原图和元数据，返回 `{"deleted":"图片ID"}` |
| `DELETE /api/albums/{album}` | 仅删除空图集；非空返回 409，成功返回 `{"deleted":"图集ID"}` |

上传和插件首次写入会自动创建图集，无需先创建。不存在的图集列图返回空列表。无效图片返回 422，上传超过 10 MiB 返回 413，原图不存在返回 404。

例如在本机开发服务上操作，`--user admin` 会提示输入密码（按实际后台用户名调整）：

```bash
curl --user admin -H 'X-Requested-With: qqbot-admin' \
  --json '{"id":"goodnight"}' http://127.0.0.1:8080/api/albums

curl --user admin -H 'X-Requested-With: qqbot-admin' \
  -H 'Content-Type: image/jpeg' --data-binary @night.jpg \
  http://127.0.0.1:8080/api/albums/goodnight/images

curl --user admin http://127.0.0.1:8080/api/albums/goodnight/images
```

上传按图片实际内容校验格式，不采纳客户端文件名。删除接口同样需要后台登录和写请求标头，不执行递归删除。

## 图片监测写入

`anime_rating_watch` 新增 `album` 参数，默认 `anime-rating-hits`，命中后调用公共图集写入原图。不同群可以覆盖目标图集。识别分数、二维闸门、来源群和消息号保存在 `metadata` 中，其余识别和回复规则保持现有行为。

旧归档目录及 `BOT_DEEPGHS_ARCHIVE_DIR` 不再用于新图片。旧图片不迁移、不参与新图集读取，本次未操作历史文件。

## 定时晚安配置

在现有管理页找到“定时晚安”，启用并添加目标群。配置参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `time` | `23:00` | 每天北京时间，24 小时制 `HH:MM` |
| `text` | `晚安，做个好梦。` | 自定义文字，可留空以仅发送图片 |
| `album` | `goodnight` | 每次随机读取一张图片的图集 ID |

时间、文案和图集都可按群覆盖。默认晚安图集与识别图集分开；需要共用时把晚安的 `album` 改为 `anime-rating-hits` 或其他已有图集。

插件每 5 秒检查当前分钟和最新配置；仅向已启用、实际已加载且处于群白名单的群发送，不发送私聊，群成员白名单不限制这类定时群任务。初次加入代码需要按现有流程更新并重启进程；之后修改时间、文案、群范围或图集立即供下一次检查使用。

每群每天尝试一次，文字和随机图片组成同一条消息。空图集或图片读取失败时只发文字，两者都为空则跳过。QQ 发送失败只记日志，不自动重试。无 QQ 连接时，若在目标分钟内恢复连接仍可发送，超过该分钟不补发。当前按单 QQ 账号使用。

当天发送标记只保存在内存，发送分钟内重启可能再次发送；当天尝试过之后修改时间不会再发。没有新增持久化任务记录或补发机制。

## 内部调用

```python
from qqbot.runtime import get_runtime

albums = get_runtime().albums
record = albums.add_image("goodnight", image_bytes, source="my_plugin",
                          metadata={"group_id": "12345"})
path = albums.random_image("goodnight")  # 空图集返回 None
```

另有 `create_album(id)`、`list_albums()`、`list_images(id)`、`image_path(album, image_id)`、`delete_image(album, image_id)`、`delete_album(id)`。调用方负责插件权限和业务判断，公共图集不依赖具体插件。文件操作是同步方法，异步处理器中放到线程执行，读取图片后用 OneBot 的 Base64 图片消息发送，无需协议端访问本机路径。
