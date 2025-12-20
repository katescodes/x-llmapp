from typing import Literal


# Unified kb document categories so ORM/routers/frontend share the same literal type.
KbCategory = Literal["history_case", "reference_rule", "general_doc", "web_snapshot", "tender_app"]


