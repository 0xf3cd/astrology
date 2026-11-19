# 发行流程

[English](../en/releasing.md) · [发行说明](releases.md) · [参与开发](contributing.md)

`Release` 工作流构建一份 sdist，并从该 sdist 构建 wheel，保留成员清单和 SHA-256，
再让七项隔离安装消费者使用同一份 wheel。只有手动触发的 main 运行，且构建和每项消费者全部成功，
才可上传这些文件。PR 运行验证构建与消费，不能发布；tag 和普通 main push 不触发本工作流。

## 检查发布边界

发行验收前，回读 main 分支保护及 GitHub 的 `pypi` environment，包括分支规则列表。
设置变更须另获维护者授权。发布边界如下：

- 使用指定部署分支／tag 的模式，只保留一条 **branch** 规则 `main`。
  不允许 PR merge ref、tag 或无限制部署。回读 environment 政策及分支规则列表；
  PR 可以修改工作流，因此仅有 workflow `if` 不够。
- 发布 job 启动前须经维护者批准。不要使用管理员权限绕过批准或部署限制。
- 保留既有 main 分支保护及独立的 Pages environment。

在 PyPI 登记 [pending Trusted Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)，
项目名 `celestial-astrology`，owner `0xf3cd`，repository `astrology`，workflow `release.yml`，
environment `pypi`。pending publisher 不保留项目名。已有项目使用其
[publisher 设置](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)。
不提供长期上传密码；缺少 publisher 或 environment 拒绝访问时应停止，不能改用 token 或放宽保护。

## 准备并检查候选

发布新版本前，另行准备并审阅版本升级及配套文档。发行说明写明交付了什么；
包索引的实际可用性记在发行记录中。

1. 审阅源码、配套双语说明，以及发行追踪单的验收条件。明确依赖政策、计算约定及不兼容的 API 变化。
2. 本地运行锁定依赖的完整检查，并运行 PR 质量／安装工作流。
   既有完整质量矩阵是 Linux 3.11／3.14 及 macOS／Windows 3.14；七项保留 wheel 的消费者是
   Linux x86_64 3.11／3.12／3.13／3.14、Linux ARM64 3.14、macOS ARM64 3.14 和 Windows amd64 3.14。
   两者检查内容不同，并未穷尽所有受支持的 Python／平台组合。
3. 检查实际 sdist／wheel 的成员和元数据，包括 sdist 的 `PKG-INFO` 和 wheel 的 `METADATA` 中的
   UTF-8 Markdown 描述。两者都包含英文 `README.md`，不是各含一份英文和中文描述。
   描述须匹配接受的 `README.md`，
   不能留下会随发布过期的候选说法。核对 README 的包名和安装命令，并用接受的包执行示例。
   检查源码及解包 sdist 生成的中英文页面：快照标签始终检查，固定 SHA 的源码／归档链接则在
   `ASTROLOGY_DOCS_SOURCE_SHA` 指定构建源码修订号时检查。
   清单记录源码提交、Python／依赖要求、
   两份制品的摘要，以及每个归档文件的路径、大小和摘要。额外成员、与源码不同的字节或运行依赖变化都会被拒绝。
4. 验证新发行检查的代表性反例。每个新 uv 步骤固定 uv 0.12.5、对应归档的 SHA-256 及新的工具缓存目录。
   在不合并的探针分支上，错误摘要必须使步骤在 uv 运行前失败，包括 ARM 消费者。
   网络错误不能作为这项证据。

本地完整检查若需保留分发文件，使用一个尚不存在的输出目录：

```sh
uv sync --locked --python 3.14
uv run --locked python tools/check.py --artifacts-dir dist/packages
```

目标目录不能已存在。该命令保留通过完整分发检查的文件，不上传，也不据此宣称已发行。
工作流的 `tools/release.py prepare` 检查源码未变，写入 `dist/manifest.json`，
并单独输出构建 job 的摘要。准备和消费都不再构建第二份发行 wheel。

README 按包名安装最新发行版，并另给源码安装入口。发行说明链接到各自版本的索引页。
实际可用性及部分完成状态记在发行记录中，并注明接受的源码 SHA、工作流运行／制品 ID 和文件摘要。
Pages 即使展示已发布版本，也仍是源码文档快照。

### 合并与发布验收

检查结果必须对应本次接受的候选。旧提交的成功运行或审阅不能算作当前提交的结果。

| 条件 | 实际保护及验收动作 |
|---|---|
| 四项完整质量检查：Linux 3.11／3.14、macOS／Windows 3.14 | main 的必需状态，严格要求分支更新后通过。合并前全部成功；批准发布前再核发布 SHA 的主干结果。 |
| Release 构建和七项同一 wheel 消费者 | 工作流依赖要求全部成功后才能发布。合并前也须检查，但它们不是额外的分支保护必需状态。 |
| 代码与安全审阅，包括 bot 发现 | 维护者验收，不是已配置的必需状态。解决阻塞意见；缺失、不可用或旧提交结果记为未执行，不能记成功。只有维护者可明确决定是否接受这些已记录的限制继续推进。 |
| 人工合并与发布授权 | 维护者分别决定；检查通过不构成授权。记录接受的精确版本、SHA 和制品。 |
| 发布 job | 仅 main 的手动运行，构建／消费者成功，并获 pypi environment 指定审阅者批准；唯一指定部署分支规则是 main。 |

实际保护或工作流与上述要求不同时，暂停受影响的验收并报告差异，不放宽设置，
也不把人工要求写成机器已强制。

### 无上传演练

发行流程或工作流变化后，若常规发布前检查仍有未覆盖的失败路径，再安排无上传演练。
核对流程步骤时，使用保留的 wheel 和 sdist 在本地执行相关步骤；核对修改后的构建／消费步骤时，
使用 PR 触发的工作流。记录缺口、wheel 和 sdist 的精确文件名及摘要、执行命令和结果。
常规发行可使用正式工作流在人工批准前完成的构建及
同一 wheel 消费检查，无须另跑演练。无上传运行不能核验 OIDC 凭据、PyPI 上传或线上部署；
这些仍须在获授权的发布及发布后验收中检查。

## 授权并运行发布

候选验收并合入后，为其版本及完整 main 提交号取得发布授权。
在 Actions 选择 `Release`、`Run workflow`，分支选 `main`，填入精确的 `version` 和 `sha`。
检出源码与请求提交或当前远端 main 不同时会被拒绝；不要用移动的分支名代替 SHA。

制品按本次构建 job 返回的精确 ID 下载，不按可复用名称或另一次运行查找。
每个消费者将 wheel／sdist 摘要与独立的构建 job 输出比较，核清单与源码一致，
然后只在仓外安装保留的 wheel。预期源码命盘由同一 runner 计算。
普通／优化模式下的知识、命盘、元数据缺失及 README 检查都须通过，不能重建发行 wheel。

批准 `pypi` 部署前检查这些结果和 `manifest.json`。
只有 Linux 发布 job 具有 `id-token: write`，且依赖构建和整个消费者矩阵。
它再次检查两份分发文件的精确名称和 SHA-256，再调用以提交号固定的 PyPI action，
启用 attestations，保持 `skip-existing: false`。它不在该权限下运行本仓构建代码。

## 核验并记录发布结果

从 PyPI 下载两份分发文件，将其字节摘要与保存清单中的 SHA-256 比较。
读取该版本的 PyPI 描述，检查包名和安装命令，并与接受的 README 及下载文件中的描述对照。
在新的受支持环境里执行 README 的包索引安装命令，再运行其中的命盘和知识示例。
源码快照安装成功不能代替包索引安装验收。

仅按发布授权，在验收的源码 SHA 上创建版本标签（`v` 加获准发布的版本号）和 GitHub Release，
附上核验后的 wheel、sdist 和清单。
GitHub 自动生成的源码 ZIP／tar 是 git 快照，不是已发布的 sdist。
回读 Release 的版本、tag 指向、描述及附件摘要，不能只凭创建请求判断成功。
发行记录写入实际工作流结果、制品身份、下载摘要、安装结果及剩余限制。
从同一份验收源码手动更新双语 Pages 站点，并检查受影响的线上页面。
检查站点根入口的版本与源码 SHA、两语 README 安装路径、发行说明和受影响的功能页，
与接受的构建对照；本地 HTML 构建成功不能证明站点已经部署。

上传成功而 tag／Release／站点步骤失败时，保留成功上传的事实并报告部分完成状态。
使用核验后的文件完成剩余交付，不重建，也不在同一版本下上传替代品。
重复文件报错不能成为启用 `skip-existing` 的理由；内容变化需要新的、经过审阅的发行版本。

## 将接受的发行镜像到 Gitee

GitHub 仍是源码正本。首次镜像前，维护者须选定公开的 Gitee 命名空间／仓库，核验权限、
双因素认证、恢复准备、全新登录及 Git／API 客户端。创建仓库、修改账户设置与发布均须获授权。
API 文档和本地测试不能证明账户有发布资格。

使用接受的完整 SHA 对应的干净 checkout，包版本须一致。从其 GitHub Release 或正式工作流制品中
保留原文件，按以下结构放置；不重建包，也不重新生成已发布的清单：

```text
release-files/
  manifest.json
  packages/
    celestial_astrology-0.6.0-py3-none-any.whl
    celestial_astrology-0.6.0.tar.gz
```

只读预检命令如下，替换仓库及 SHA 占位符：

```sh
uv run --locked python tools/mirror.py check --version 0.6.0 --sha ACCEPTED_FULL_SHA --repository NAMESPACE/REPOSITORY --branch main --files release-files
```

保留文件应放在 checkout 外。`check` 使用匿名读取，不写远端。它核验 GitHub tag 及稳定 Release 的
已上传附件，包括各文件原始大小和 SHA-256，再用 PyPI 交叉核对两份分发文件的摘要，
然后检查原清单及归档与源码一致，不安装、不重建。无关的摘要环境变量不参与判断。
接受的旧发行不必仍是 GitHub main 的当前尖端。

另获发布授权后，将同一命令的 `check` 换成 `publish`。操作者通过进程环境提供 API 写入所需的
`GITEE_ACCESS_TOKEN`，并另行建立 Git 认证。凭据不得放进 URL、命令参数或保留日志。
工具不安装认证文件或 helper，禁用交互提示。匿名 Git 读取不继承操作者的凭据、URL 重写或额外请求头。
API 写入使用固定的 HTTPS Gitee 来源、文档规定的表单／multipart token 字段，并拒绝重定向。

只允许写选定的 `refs/heads/main`（或显式指定的着陆分支）及 `refs/tags/v0.6.0`，
两者均须解析到接受的提交。分支更新必须是已知的快进；已有且相符的附注 tag 在剥离后保留。
已有仓库的默认分支须匹配着陆分支。空仓库可接收首个选定分支，但创建 Release 前须回读默认分支；
不符时停止，另行授权操作者配置。工具不强推、不镜像全部 ref、不创建 webhook，也不自动改设置。
分支已领先、分叉或祖先关系未知时失败；新版已推进分支后再补旧版的部分镜像，需要操作者介入。

Release 正文取自接受的 Git 对象中 `docs/zh-CN/releases.md` 的精确版本小节，使用指向 tag 的绝对指南链接；
比较时只规范 CRLF。相同的元数据和附件保留。附件完整分页读取，上限为每页 100 条、20 页；
JSON 响应限 2 MiB，每个原文件限 64 MiB。缺失文件使用通过核验的同一份不可变字节缓冲上传。
重名、意外文件名或下载字节不同均报错并给出附件 ID。Git 自带的源码归档不算上传附件。

写入失败或超时后，工具匿名回读，不自动重试该写入。观察到相符结果则保留；
状态未确认则停止。显式重跑前先检查部分交付，重跑重新盘点远端，只从原文件补齐缺失内容。
工具不删除冲突，也不回滚已完成的工作，不打印 HTTP／Git 错误正文。

匿名附件下载及其重定向只允许标准端口上的 HTTPS `gitee.com`。未知来源会失败；
账户验收时应查明实际平台行为，不自动放宽政策。回读不发送 API 凭据。

记录接受的版本／SHA、ref 目标、说明、附件 ID 和匿名下载摘要。检查实际 Gitee 首页及中文 README
选择、中文发行说明渲染和源码链接。Gitee 文档中的 README 语言后缀规则不能代替渲染验收。
三份匿名下载均须与保留文件核对。仅 Git 传输成功不算镜像验收完成；
准备工作不关闭发行追踪单或镜像 issue。
