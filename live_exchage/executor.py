from utils.logger import global_logger as logger


class TradeExecutor:
    def __init__(self, ledger_manager):
        self.ledger_manager = ledger_manager

    def execute(self, symbol, sym_name, action, intent_shares, price, reason, account, current_date_str):
        cost = account.get_avg_price(symbol)
        held_shares = account.get_shares(symbol)
        trade_result = account.execute_trade(symbol=symbol, action=action, shares=intent_shares, price=price,
                                             current_time=current_date_str)

        if trade_result['success']:
            filled_shares = trade_result['filled_shares']
            profit_pct = (price - cost) / cost if cost > 0 else 0

            action_cn = "建议卖出" if action == "SELL" else "建议买入"
            self.ledger_manager.append_live_ledger_with_reason(current_date_str, symbol, sym_name, action_cn,
                                                               filled_shares, price, reason, status="待确认")

            if action == "SELL":
                log_msg = f"🔴 {symbol} ({sym_name}) 建议卖出 {filled_shares} 股 | 预估价: {price:.2f} | 状态: 待老板确认 | 逻辑: {reason}"
                return True, log_msg, "SELL"
            else:
                account.positions[symbol].buy_date = current_date_str
                account.positions[symbol].buy_reason = reason
                log_msg = f"🟢 {symbol} ({sym_name}) 建议买入 {filled_shares} 股 | 预估价: {price:.2f} | 状态: 待老板确认 | 逻辑: {reason}"
                return True, log_msg, "BUY"
        else:
            return False, f"⛔ {symbol} ({sym_name}) 拦截: 试图 {action} {intent_shares} 股。原因: {trade_result['message']}", "REJECT"