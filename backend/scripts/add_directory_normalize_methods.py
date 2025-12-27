"""
临时脚本：在 TenderService 类中添加 normalize 方法
这些方法应该插入到 generate_directory 方法之后，_build_directory_tree 方法之前
"""

NORMALIZE_METHODS = '''
    # ==================== 目录规范化方法（通用版） ====================
    
    def _bucket_by_title(self, title: str) -> str:
        """根据标题内容判断所属分桶"""
        import re
        _BUCKET_PRICE = re.compile(r"(报价|价格|明细|汇总|总价|分项|报价表|报价单|投标报价|磋商报价|报价响应)", re.I)
        _BUCKET_TECH  = re.compile(r"(技术|方案|规格|参数|偏离|样本|手册|实施|组织|架构|测试|配置|选型|技术规格)", re.I)
        _BUCKET_BIZ   = re.compile(r"(营业执照|资质|证书|社保|信用|授权|委托|承诺|声明|基本情况|信誉|自评|证明|建议|不转包|分包)", re.I)
        
        t = (title or "").strip()
        if not t:
            return "unknown"
        if _BUCKET_PRICE.search(t):
            return "price"
        if _BUCKET_TECH.search(t):
            return "tech"
        if _BUCKET_BIZ.search(t):
            return "biz"
        return "unknown"
    
    def _infer_parent_index_by_level(self, nodes: list) -> list:
        """根据 level 推断父节点索引"""
        parent = [-1] * len(nodes)
        stack = []  # [(level, index)]
        for i, n in enumerate(nodes):
            lv = int(n.get("level") or 1)
            while stack and stack[-1][0] >= lv:
                stack.pop()
            parent[i] = stack[-1][1] if stack else -1
            stack.append((lv, i))
        return parent
    
    def _find_section_titles(self, nodes: list) -> dict:
        """查找三分册和 wrapper 标题"""
        import re
        _WRAPPER_RE = re.compile(r"(投标文件|响应文件|磋商响应文件|投标响应文件|响应文件目录|投标文件目录)", re.I)
        _SECTION_BIZ_RE = re.compile(r"(资信|商务|资格)", re.I)
        _SECTION_TECH_RE = re.compile(r"(技术)", re.I)
        _SECTION_PRICE_RE = re.compile(r"(报价|价格|磋商报价|报价响应)", re.I)
        
        biz = tech = price = wrapper = None
        for n in nodes:
            title = (n.get("title") or "").strip()
            if not title:
                continue
            if wrapper is None and _WRAPPER_RE.search(title):
                wrapper = title
            if biz is None and _SECTION_BIZ_RE.search(title):
                biz = title
            if tech is None and _SECTION_TECH_RE.search(title):
                tech = title
            if price is None and _SECTION_PRICE_RE.search(title):
                price = title
        return {"biz": biz, "tech": tech, "price": price, "wrapper": wrapper}
    
    def _collapse_wrapper(self, nodes: list) -> list:
        """折叠 wrapper 节点（投标文件/响应文件等总标题）"""
        from collections import deque
        
        if not nodes:
            return nodes
        sec = self._find_section_titles(nodes)
        wrapper = sec["wrapper"]
        if not wrapper:
            return nodes
        if not (sec["biz"] and sec["tech"] and sec["price"]):
            return nodes

        title_to_first_idx = {}
        for i, n in enumerate(nodes):
            t = (n.get("title") or "").strip()
            if t and t not in title_to_first_idx:
                title_to_first_idx[t] = i

        w_idx = title_to_first_idx.get(wrapper)
        if w_idx is None:
            return nodes

        parent = self._infer_parent_index_by_level(nodes)
        children = [[] for _ in nodes]
        for i, p in enumerate(parent):
            if p >= 0:
                children[p].append(i)

        sub = set()
        q = deque([w_idx])
        while q:
            x = q.popleft()
            sub.add(x)
            for c in children[x]:
                q.append(c)

        # 三分册必须都在 wrapper 子树里才折叠（避免误伤）
        b = title_to_first_idx.get(sec["biz"])
        t = title_to_first_idx.get(sec["tech"])
        p = title_to_first_idx.get(sec["price"])
        if not (b in sub and t in sub and p in sub):
            return nodes

        new_nodes = []
        for i, n in enumerate(nodes):
            if i == w_idx:
                continue  # remove wrapper
            nn = dict(n)
            if i in sub:
                lv = int(nn.get("level") or 1)
                nn["level"] = max(1, lv - 1)
                title = (nn.get("title") or "").strip()
                if title in (sec["biz"], sec["tech"], sec["price"]):
                    nn["parent_ref"] = ""
            new_nodes.append(nn)

        return new_nodes
    
    def _ensure_sections_are_level1(self, nodes: list) -> list:
        """确保三分册为一级标题"""
        if not nodes:
            return nodes
        sec = self._find_section_titles(nodes)
        if not (sec["biz"] and sec["tech"] and sec["price"]):
            return nodes

        title_to_first_idx = {}
        for i, n in enumerate(nodes):
            t = (n.get("title") or "").strip()
            if t and t not in title_to_first_idx:
                title_to_first_idx[t] = i

        idxs = [title_to_first_idx.get(sec["biz"]), title_to_first_idx.get(sec["tech"]), title_to_first_idx.get(sec["price"])]
        if any(i is None for i in idxs):
            return nodes

        new_nodes = [dict(n) for n in nodes]
        for i in idxs:
            new_nodes[i]["level"] = 1
            new_nodes[i]["parent_ref"] = ""

        # 顶层分册 order_no 按出现顺序重排
        top_seq = 1
        for i in sorted(idxs):
            new_nodes[i]["order_no"] = top_seq
            top_seq += 1

        return new_nodes
    
    def _rebucket_to_sections(self, nodes: list) -> list:
        """语义分桶纠偏：把条目挂到正确分册"""
        from collections import defaultdict
        
        if not nodes:
            return nodes
        sec = self._find_section_titles(nodes)
        if not (sec["biz"] and sec["tech"] and sec["price"]):
            return nodes

        biz_title, tech_title, price_title = sec["biz"], sec["tech"], sec["price"]
        section_titles = {biz_title, tech_title, price_title}

        new_nodes = [dict(n) for n in nodes]

        # 判断是否"全挂报价"的典型错挂，触发 aggressive
        cnt = defaultdict(int)
        for n in new_nodes:
            pr = (n.get("parent_ref") or "").strip()
            if pr in section_titles:
                cnt[pr] += 1
        aggressive = (cnt.get(biz_title, 0) == 0 and cnt.get(tech_title, 0) == 0 and cnt.get(price_title, 0) >= 6)

        for n in new_nodes:
            title = (n.get("title") or "").strip()
            if not title:
                continue
            if title in section_titles:
                continue
            import re
            _WRAPPER_RE = re.compile(r"(投标文件|响应文件|磋商响应文件|投标响应文件|响应文件目录|投标文件目录)", re.I)
            if _WRAPPER_RE.search(title):
                continue  # 兜底：wrapper残留不处理

            bucket = self._bucket_by_title(title)
            if bucket == "unknown":
                continue

            target_parent = {"biz": biz_title, "tech": tech_title, "price": price_title}[bucket]
            cur_pr = (n.get("parent_ref") or "").strip()

            # aggressive 或者明显错挂/无挂载 -> 纠偏
            if aggressive or cur_pr in ("", price_title) or cur_pr not in section_titles:
                n["parent_ref"] = target_parent
                n["level"] = 2  # 压缩到分册下二级，保证稳定可用

        # 分册下二级节点 order_no 稳定重排（按原出现顺序）
        bucket_items = defaultdict(list)
        for idx, n in enumerate(new_nodes):
            if int(n.get("level") or 1) == 2:
                pr = (n.get("parent_ref") or "").strip()
                if pr in section_titles:
                    bucket_items[pr].append((idx, n))

        for pr, items in bucket_items.items():
            items.sort(key=lambda x: x[0])
            seq = 1
            for _, n in items:
                n["order_no"] = seq
                seq += 1

        return new_nodes
    
    def _normalize_directory_nodes(self, nodes: list) -> list:
        """通用目录规范化：wrapper折叠 + 三分册一级 + 语义纠偏"""
        nodes = nodes or []
        nodes = self._collapse_wrapper(nodes)
        nodes = self._ensure_sections_are_level1(nodes)
        nodes = self._rebucket_to_sections(nodes)
        return nodes
'''

if __name__ == "__main__":
    print("请手动将以上方法插入到 TenderService 类中")
    print("位置：generate_directory 方法之后，_build_directory_tree 方法之前")
    print(NORMALIZE_METHODS)

