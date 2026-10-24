# 发行流程

[English](../en/releasing.md) · [发行说明](releases.md) · [参与开发](contributing.md)

`Release` 工作流构建一份 sdist，并从该 sdist 构建 wheel，保留成员清单和 SHA-256，
再让七项隔离安装消费者使用同一份 wheel。只有手动触发的 main 运行，且构建和每项消费者全部成功，
才可上传这些文件。PR 运行验证构建与消费，不能发布；tag 和普通 main push 不触发本工作流。

## 先配置发布边界

首次 PR 验证或登记 publisher 前，配置 GitHub 的 `pypi` environment：

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

1. 审阅源码、配套双语说明，以及发行追踪单的七项验收。明确依赖政策、计算约定及不兼容的 API 变化。
2. 本地运行锁定依赖的完整检查，并运行 PR 质量／安装工作流。
   既有完整质量矩阵是 Linux 3.11／3.14 及 macOS／Windows 3.14；七项保留 wheel 的消费者是
   Linux x86_64 3.11／3.12／3.13／3.14、Linux ARM64 3.14、macOS ARM64 3.14 和 Windows amd64 3.14。
   两者检查内容不同，并未穷尽所有受支持的 Python／平台组合。
3. 检查实际 sdist／wheel 的成员和元数据。清单记录源码提交、语料版本、Python／依赖要求、
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
在新的受支持环境里执行 README 的包索引安装命令，再运行其中的命盘和知识示例。
源码快照安装成功不能代替包索引安装验收。

仅按发布授权，在验收的源码 SHA 上创建 `v0.1.0` 和 GitHub Release，附上核验后的 wheel、sdist 和清单。
GitHub 自动生成的源码 ZIP／tar 是 git 快照，不是已发布的 sdist。
发行记录写入实际工作流结果、制品身份、下载摘要、安装结果及剩余限制。
从同一份验收源码手动更新双语 Pages 站点，并检查受影响的线上页面。

上传成功而 tag／Release／站点步骤失败时，保留成功上传的事实并报告部分完成状态。
使用核验后的文件完成剩余交付，不重建，也不在同一版本下上传替代品。
重复文件报错不能成为启用 `skip-existing` 的理由；内容变化需要新的、经过审阅的发行版本。
