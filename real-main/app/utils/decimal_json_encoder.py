from decimal import Decimal
from json import JSONEncoder


class DecimalJsonEncoder(JSONEncoder):
    "Helper class that can handle encoding decimals into json (as floats, percision lost)"

    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalJsonEncoder, self).default(obj)
