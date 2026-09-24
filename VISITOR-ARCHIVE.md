# 访客统计长期归档（免费方案）

已接入的 Umami 继续记录实时数据；此归档独立保存每个自然月的汇总，不受 Umami 云端六个月保留期影响。**它需要定期导入，不会自行读取 Umami，也不会自动备份未来的数据。** 建议每月结束后尽快导出上一个月，最迟不要等到六个月的保留窗口过去。

## 已保存什么

- `files/visitor-history.json`：长期主档，逐月保存原始访客数、访问次数、页面浏览量，以及完整国家/地区和城市计数。
- `files/visitor-history.html`：可独立打开的历史统计页面，支持月份选择、国家/城市切换、搜索、数量与百分比；公开页面只含汇总，不含 IP、访问者标识或逐次访问明细。
- `local/visitor-archive/exports/`：本机保存的原始地区 CSV，按月份和文件摘要命名。它不进入网站发布包，也不上传到 GitHub；请额外备份本机目录。
- `local/visitor-archive/backups/`：重新导入前的本机 JSON 恢复副本。GitHub 中提交过的 JSON 版本另有版本历史。

第一份是 **2026 年 9 月的未结束月份快照**，仅保存截至 24 September 2026 14:26 UTC 的 13 位月度访客、13 次访问、17 次浏览、12 个国家/地区及 12 个城市。这些数据包含建站与 VPN 测试访问。9 月结束后需重新导出完整 9 月数据覆盖此快照。Umami 自 24 September 2026 开始采集；此前 MapMyVisitors 的历史仍由原服务保留，未混入该归档。

## 每月怎么导出

1. 登录 Umami，打开 **Elton / hcmx1994.github.io**。统一使用 **Europe/London** 时区，清除所有路径、国家等筛选条件。
2. 日期选 **This month** 后点击前一周期箭头，或通过 **Custom range** 选择上一个完整自然月。不要选滚动的 Last 30 days。记录顶部 **Visitors、Visits、Views** 三个数。
3. 在 **Location → Countries → More** 打开明细，点击下载图标，得到 `country.csv`。
4. 在明细左侧选择 **City**，点击下载图标，得到 `city.csv`。必须导出完整明细，不要仅复制首页前十条地区。留意分页和筛选。
5. 将两个 CSV、统计月份、三个总数和时区提供给 Codex，即可核对并更新长期档案。账户 Settings → Data 的完整原始数据导出是另一种格式，不要直接传给下方汇总导入命令。

从已登录后台导出这些地区明细不需要 API key 或付费 API。

## 导入与发布

以下是**已结束月份**的命令模板，请将月份、文件路径和三个总数替换为后台实际值：

```powershell
python scripts/archive_visitors.py --month YYYY-MM --countries 'path/to/country.csv' --cities 'path/to/city.csv' --visitors VISITORS --visits VISITS --pageviews VIEWS --timezone Europe/London --complete
python scripts/test_archive_visitors.py
python scripts/build_site.py
python scripts/check_site.py
```

导入当前未结束月份时，**不要加 `--complete`**。同一月份重新导入会替换该月，而不是与旧快照相加；其他月份保持不变。工具拒绝旧时间覆盖新快照、汇总数量不一致、不完整地区表、地区重复行和统计时区混用。数量下降时先核对筛选和导出范围，只有确认是统计服务修正才使用 `--allow-correction`。

更新后提交 `files/visitor-history.json` 和 `files/visitor-history.html` 到 GitHub 默认分支，网站原有 GitHub Actions 会发布它们。此后导入只需更新这两个文件。`python scripts/archive_visitors.py --render-only` 可从主档重建 HTML，不访问 Umami。

## 统计口径

- **访客数**：每个自然月原样保存 Umami 的 Visitors；同一个人可能跨月再次访问，不能把月度访客相加当作全历史去重人数。
- **访问次数和浏览量**：不重叠月份可直接累加。全档案页展示这两项累计数，不宣称是全历史唯一自然人数。
- **地区占比**：某地访问次数 ÷ 所选月份全部访问次数。未知国家/城市也保留并计入分母；搜索地区不会改变占比分母。
- **覆盖范围**：页面明确列出已经归档的月份和未完成快照，未归档月份不是零访问。归档只累计已保存数据，不会复原服务已经过期或原本未记录的数据。
- **跨服务**：MapMyVisitors 和 Umami 重叠期间的数据不相加，防止同一次访问算两次；主页原有地图及计数继续使用 MapMyVisitors。

## 长期保管

保留 GitHub 主档、原始 CSV 和一份你自己的独立备份。每月按上述步骤补齐已结束月份，数据就能持续累积，而不依赖 Umami 保留所有历史。没有按时导入的新数据不会自动出现在历史档案中。
