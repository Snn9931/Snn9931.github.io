# GitHub 中文项目排行榜 · 静态站

数据来自 [ChHsiching/GitHub-Chinese-Top-Charts-Classified](https://github.com/ChHsiching/GitHub-Chinese-Top-Charts-Classified)（源项目 [GitHub-Chinese-Top-Charts](https://github.com/ChHsiching/GitHub-Chinese-Top-Charts)）。

在线访问：<https://Snn9931.github.io/>

## 功能

- 三榜切换：总榜 / 增速榜 / 新秀榜
- 分类切换：软件类 / 资料类
- 30 种语言分榜 + 全部语言
- 关键词搜索（仓库名 / 描述 / 作者）、Stars 排序
- Top 15 Stars 柱状图（ECharts）
- 响应式：桌面与手机均可浏览

## 更新机制

GitHub Actions（`.github/workflows/update.yml`）每周自动从数据源拉取最新榜单并重建 `index.html`，提交后由 GitHub Pages 自动发布。

## 本地重建

```bash
python build_site.py --download   # 在线拉取最新数据并生成 index.html
python build_site.py --data DIR   # 使用本地已解压的数据目录
```
