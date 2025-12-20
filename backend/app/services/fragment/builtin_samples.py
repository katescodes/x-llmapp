"""
内置范本库（最小可用）

用于旧项目缺少招标书 docx 二进制时的 fallback：
- 不保证与招标书格式 100% 一致
- 目标是“功能可用 + 用户可编辑 + 可导出”

占位符（后续可替换/渲染）：
- {{projectName}}
- {{bidderName}}
- {{date}}
"""

from __future__ import annotations

from app.services.fragment.fragment_type import FragmentType

BUILTIN_SAMPLE_HTML_BY_TYPE: dict[FragmentType, str] = {
    FragmentType.BID_LETTER: """
<h2>投标函</h2>
<p>致：{{projectName}}</p>
<p>我们已仔细阅读并理解招标文件的全部内容，愿意按照招标文件要求提供投标文件并承担相应责任。</p>
<p>如我方中标，我方承诺按招标文件及合同约定履行义务。</p>
<p style="margin-top: 24px;">投标人：{{bidderName}}</p>
<p>日期：{{date}}</p>
""".strip(),
    FragmentType.LEGAL_REP_AUTHORIZATION: """
<h2>授权委托书（法定代表人授权书）</h2>
<p>本人（姓名）________，系（投标人名称）{{bidderName}} 的法定代表人，现授权（姓名）________ 为我方合法代理人，参加 {{projectName}} 投标活动。</p>
<p>授权范围：签署与本项目投标有关的所有文件、参加开标、澄清、谈判以及签署合同等。</p>
<p>授权期限：自本授权书签署之日起至本项目合同签署完成之日止。</p>
<p style="margin-top: 24px;">投标人：{{bidderName}}</p>
<p>法定代表人（签字/盖章）：________</p>
<p>日期：{{date}}</p>
""".strip(),
    FragmentType.BID_OPENING_SCHEDULE: """
<h2>开标一览表 / 报价表</h2>
<table border="1" cellspacing="0" cellpadding="6">
  <thead>
    <tr><th>序号</th><th>报价项目</th><th>报价（元）</th><th>备注</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>________</td><td>________</td><td>________</td></tr>
    <tr><td>2</td><td>________</td><td>________</td><td>________</td></tr>
    <tr><td>3</td><td>________</td><td>________</td><td>________</td></tr>
  </tbody>
</table>
<p style="margin-top: 16px;">投标人：{{bidderName}}</p>
<p>日期：{{date}}</p>
""".strip(),
}


