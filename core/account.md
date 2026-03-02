“使用说明书”：

---

### 📖 第一部分：`Portfolio` 类 (资金大管家)

这是整个账户的核心，它负责预算隔离和流水记录。

**🔒 核心属性 (Attributes)**

- `account.sub_budgets`: `Dict[str, float]` - **核心机制**。每只股票独立分配的可用预算（例如 `{"300308": 50000.0}`）。

- `account.positions`: `Dict[str, Position]` - **持仓账本**。Key 是股票代码，Value 是下方的 `Position` 实例对象（绝不是数字！）。

**📊 动态属性 (只读 Properties)**

- `account.total_cash` -> `float`: 返回当前总可用现金（中央池 + 各股剩余预算）。不能直接被赋值！

**🔍 查询接口 (Query Methods)**

- `account.has_position(symbol) -> bool`: 查询是否持有某只股票。

- `account.get_position(symbol) -> Position`: 直接获取某只股票的 `Position` 对象。

- `account.get_shares(symbol) -> int`: 获取某只股票的持仓股数。

- `account.get_avg_price(symbol) -> float`: 获取持仓的加权平均成本价。

- `account.get_allocated_cash(symbol) -> float`: 获取某只股票还剩多少钱可以买。

- `account.get_symbol_book_value(symbol) -> float`: 获取某只股票的总资产（买入花费的成本 + 剩余可用预算）。

---

### 📖 第二部分：`Position` 类 (单只股票档案)

存在 `account.positions` 字典里的每一个元素，都是这个对象。

**🔒 核心属性 (Attributes)**

- `pos.symbol`: `str` - 股票代码。

- `pos.shares`: `int` - 当前持仓股数。

- `pos.avg_price`: `float` - 持仓成本均价。

- `pos.first_buy_time`: `datetime` - 首次建仓的时间戳。

**📊 动态属性 (只读 Properties)**

- `pos.cost` -> `float`: 当前该股票占用的总成本（股数 × 成本价）。
