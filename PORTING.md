# 移植到 DeepSeek Harness、Claude Code 或其他宿主

仓库中的角色图片完整，可用于精灵动画桌宠。每套含 **73 个透明原帧：57 个标准动作帧 + 16 个视线方向**。这些是普通 PNG 像素，不需要原作者的账号、Pets 服务或模型 API 密钥即可读取。

本仓库提供素材、逐帧包、导出工具和接入说明。DeepSeek Harness / Claude Code 的事件接入仍需在目标宿主中实现；这里没有声称已安装或实测完整宿主插件。

## 最快取用

1. 在 GitHub 点 **Code → Download ZIP**，解压整个仓库。
2. 再解压根目录的 **[portable-frames.zip](portable-frames.zip)**。其中每个角色有 9 个动作目录及 `look/`，PNG 均为透明 **192 × 208**，保留统一画布。
3. 用包内 `portable-manifest.json` 读取每帧路径、时长、播放方式及 SHA-256。单动作按列表顺序播放；`look` 是按方向选取的静态帧。
4. 若宿主支持图集，直接加载 `pets__角色__spritesheet.png` 和 **[animation-map.json](animation-map.json)**，无需拆图。

`portable-frames.zip` 已生成，无需安装 Python。想重新导出或仅导出一个角色时，在完整仓库目录运行：

```sh
python -m pip install Pillow
python export_frames.py --output portable-frames
```

单角色导出示例：`python export_frames.py --character 角色ID --output my-frames`。可用 ID 见 `animation-map.json` 的 `characters`；将 `角色ID` 换成真实 ID，如 `fenny`、`bonnie`、`pass-v3`、`casual-v3` 或 `kimono-v3`，仅选当前仓库包含的角色。输出目录必须是新目录或空目录。

导出器先校验源 PNG 的 SHA-256，再无损裁切，不缩放、不裁掉透明边缘、不生成新图。产物清单还记录每帧的原图坐标和原始 RGBA 像素哈希。

## 哪些是正式素材

| 文件 | 用途 |
| --- | --- |
| `pets__角色__spritesheet.png` | 完整透明图集，包含全部 73 帧，首选移植源 |
| `portable-frames.zip` | 同一批像素的独立透明 PNG，方便接入不支持图集的宿主 |
| `pets__角色__states__动作.gif` | 9 类独立动作，透明 192 × 208；支持透明 GIF 的宿主可使用 |
| `animation-map.json` | 明确的零基行号、有效帧数、每帧毫秒时长、角色文件和源图哈希 |
| `all-actions.gif`、`look-loop.gif`、MP4、总览 PNG、样图 | 演示或检查用；部分带背景、标题，不能替代透明运行素材 |
| `timeline.json` | 连续演示的帧起始时间；运行时用 `animation-map.json` 的逐帧时长更直接 |

16 个透明视线帧已包含在图集最后两行，以及逐帧包的 `look/`。`look-loop.gif` 是带标题的演示卡片。仓库未提供 PSD、Live2D 骨骼或分层工程；精灵动画播放不需要这些工程文件。

## 图集与播放约定

图集为 RGBA PNG，1536 × 2288，8 列 × 11 行；每格 192 × 208。坐标原点在左上角，行列从 0 开始。

| 状态 ID | 零基行号 | 有效帧数 | 语义 |
| --- | ---: | ---: | --- |
| `idle` | 0 | 6 | 待机 |
| `running-right` | 1 | 8 | 向右移动 |
| `running-left` | 2 | 8 | 向左移动 |
| `waving` | 3 | 4 | 招手 |
| `jumping` | 4 | 5 | 跳跃 |
| `failed` | 5 | 8 | 失落或失败反应 |
| `waiting` | 6 | 6 | 等待用户回应 |
| `running` | 7 | 6 | **工作／思考，不是走路** |
| `review` | 8 | 6 | 复查 |

动作第 `i` 帧的裁切矩形为 `(i*192, row*208, 192, 208)`。只播放 `frame_count` 内的格子；前九行有 15 个备用透明格，不能当作动画帧。各帧时长并不相同，以 JSON 的 `durations_ms` 为准。

视线索引 `d=0..15`：`row=9+floor(d/8)`、`column=d%8`，角度为 `d*22.5°`。0° 向上，90° 向右，180° 向下，270° 向左，按屏幕方向顺时针排列。它描述视线朝向，不是连续行走方向。静态视线帧没有必须播放的时长。

所有帧使用同一画布和锚点，建议锚点为单帧底部中心 `(96,208)`。改变显示大小时整体等比缩放，不逐帧自动裁边，否则角色可能抖动。保持 PNG 的 alpha 通道。

`playback` 的 loop/once 是本包的接入建议，可以按宿主交互调整。招手、跳跃、失败反应默认播一次再回到当前语义状态；新事件可以打断旧动画。不要把完整的 8.84 秒演示时间线当作 Agent 必须依次播放的流程。

最小 Canvas 裁切示例（`atlas` 为已加载的 PNG，`row/column` 来自映射）：

```js
canvas.width = 192;
canvas.height = 208;
ctx.clearRect(0, 0, 192, 208);
ctx.drawImage(atlas, column * 192, row * 208, 192, 208,
              0, 0, 192, 208);
```

真梦梓名称中的 **V3 是美术版本**；图集采用的是 **Pets v2 格式**。接入旧的 8×9 图集宿主时，前九行动作可以按规则转换，最后两行视线需要另外保存和接入，不能直接丢掉并称为完整移植。

## DeepSeek Harness

官方项目为 [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)。其客户端插件可注册 React UI，官方演示与 slot catalog 包含 `shell.overlay` 浮动层。

建议在插件中加载本地图集与映射，通过 `ctx.slots.inject()` / `ctx.slots.register()` 接入合适的 UI slot，在 overlay 内用 Canvas 或 CSS background-position 播放。具体插件结构和注册参数以安装版本的官方文档为准；本素材包不绑定某个社区桌宠插件的私有格式。

建议在会话事件层处理 `turn/start`、`step/start`、`tool/call`、`tool/result`、`turn/end` 等，再转换为下面的素材状态。等待审批、等待输入和错误应读取对应的明确状态，不能只靠工具名称猜测。

官方资料：[插件开发](https://deepseek-harness.github.io/deepseek-harness/en/develop/basic/) · [Slots](https://deepseek-harness.github.io/deepseek-harness/en/reference/subsystems/slots) · [Agent 生命周期](https://deepseek-harness.github.io/deepseek-harness/en/reference/agent-lifecycle)。

## Claude Code

可通过官方 **hooks + 本机播放器／悬浮窗** 实现状态联动。命令 hook 从标准输入接收 JSON；桥接程序只需读取事件类型，转换成有限的动作状态交给播放器。PNG 素材本身不等同于已经安装好的 Claude Code 插件。

| 语义 | Claude Code hook | DeepSeek Harness 对应信号 | 建议素材动作 |
| --- | --- | --- | --- |
| 会话开始 | `SessionStart` | 会话打开 | `waving` 后 `idle` |
| 正在工作 | `UserPromptSubmit`、`PreToolUse` | `turn/start`、`step/start`、`tool/call` | `running` |
| 等待用户 | `PermissionRequest`；`Notification` 的 `permission_prompt` / `idle_prompt` | 明确的审批或输入等待状态 | `waiting` |
| 工具返回 | `PostToolUse` | `tool/result` | 短暂 `review` 后恢复工作态 |
| 错误 | `PostToolUseFailure`、`StopFailure` | 明确失败结果或事件 | `failed` |
| 回复结束 | `Stop` | `turn/end` | `idle` |
| 会话关闭 | `SessionEnd` | 会话关闭 | `idle` 或隐藏 |

上表是本包的适配建议，不是两个产品共同定义的宠物协议。Claude 的 `Stop` 表示主 Agent 结束回复，不能直接解释成任务成功；用户中断、权限拒绝和工具执行失败也可能走不同事件，适配器应分别处理。

推荐桥接消息仅含诸如 `{"state":"running"}` 的本机显示状态。正常 hook 以 `exit 0` 结束，不输出阻断决策；无需把提示词、工具参数、完整 hook payload、聊天记录或 API 密钥写入素材包。

官方资料：[Claude Code hooks 参考](https://code.claude.com/docs/en/hooks)。事件名称、匹配器和配置位置应以所用版本为准。

## 移植验收

- 每个角色：9 个动作共 57 帧，另有 16 个视线帧，总计 73 帧。
- PNG 保留透明通道，单帧 192 × 208，帧序和时长与 JSON 一致。
- 待机、工作、等待、错误、回复结束各能触发正确状态；工作不误播水平移动。
- 关闭或切换会话后不遗留旧动画状态；多会话场景明确当前跟随的会话。
- 先独立验证图像播放，再接宿主事件；本包已验证素材导出，完整宿主适配仍应在目标版本运行验收。
