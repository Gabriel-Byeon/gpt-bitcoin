import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pyupbit  # 현재 BTC 가격을 가져오기 위함

# 데이터베이스 연결 함수
def get_connection():
    return sqlite3.connect('bitcoin_trades.db')

# 데이터 로드 함수 (캐싱 비활성화)
def load_data():
    conn = get_connection()
    query = "SELECT * FROM trades"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# 실현 수익 계산 함수 (비트코인 매매 수익만 계산)
def calculate_realized_profit(df):
    realized_profit = 0
    for i in range(1, len(df)):
        if df.iloc[i]['decision'] == 'sell' and df.iloc[i-1]['decision'] == 'buy':
            btc_sold = df.iloc[i-1]['btc_balance'] - df.iloc[i]['btc_balance']
            sell_price = df.iloc[i]['btc_krw_price']
            buy_price = df.iloc[i-1]['btc_avg_buy_price']
            realized_profit += btc_sold * (sell_price - buy_price)
    return realized_profit

# 추가 자금 계산 함수 (입금 - 출금 반영, DB에만 저장된 정보)
def calculate_net_funds(df):
    additional_funds = df['external_deposit'].sum() - df['external_withdrawal'].sum() if 'external_deposit' in df.columns and 'external_withdrawal' in df.columns else 0
    return additional_funds

# 총 투자 자금 계산 함수 (초기 투자금 + 추가 자금 - 출금)
def calculate_total_investment(df):
    initial_krw_balance = df.iloc[0]['krw_balance']
    initial_btc_balance = df.iloc[0]['btc_balance']
    initial_btc_price = df.iloc[0]['btc_krw_price']
    
    # 초기 투자금 계산
    initial_total_investment = initial_krw_balance + (initial_btc_balance * initial_btc_price)
    
    # 순 자금 계산 (입금 - 출금)
    net_funds = calculate_net_funds(df)
    
    # 총 투자금 = 초기 투자금 + 순 자금
    total_investment = initial_total_investment + net_funds
    return total_investment

# 현재 자산(현금 + 비트코인 자산) 계산 함수 (추가금 반영 안됨)
def calculate_current_assets(df):
    current_krw_balance = df.iloc[-1]['krw_balance']
    current_btc_balance = df.iloc[-1]['btc_balance']
    current_btc_price = pyupbit.get_current_price("KRW-BTC")  # 실시간 BTC 가격 가져오기

    # 현재 총 자산 (현금 + 보유한 비트코인 자산)
    current_assets = current_krw_balance + (current_btc_balance * current_btc_price)
    return current_assets

# 실제 투자된 금액(비트코인에 투자된 금액)
def calculate_invested_amount(df):
    current_btc_balance = df.iloc[-1]['btc_balance']
    current_btc_price = pyupbit.get_current_price("KRW-BTC")  # 실시간 BTC 가격 가져오기

    # 현재 BTC 보유 잔액에 대한 자산 가치
    invested_amount = current_btc_balance * current_btc_price
    return invested_amount

# 매도 시 비트코인에 의한 수익과 추가 자금 비교
def compare_profit_vs_funds(df):
    total_realized_profit = calculate_realized_profit(df)  # 비트코인 매매로 인한 수익
    net_funds = calculate_net_funds(df)  # 입금에서 출금을 뺀 순 자금
    
    st.write(f"총 실현 수익(비트코인): {total_realized_profit:.0f} 원")
    st.write(f"순 추가 자금 (입금 - 출금): {net_funds:.0f} 원")
    
    # 비교
    if total_realized_profit > net_funds:
        st.write("비트코인 매매로 더 많은 수익을 냈습니다.")
    else:
        st.write("추가 자금이 더 많습니다.")

# 외부 입금 내역 기록 함수
def record_external_deposit(deposit_amount):
    conn = get_connection()
    c = conn.cursor()
    
    # 최신 거래 이후로 입금 금액을 기록 (DB에만 반영)
    c.execute('''UPDATE trades SET external_deposit = ? WHERE id = (SELECT MAX(id) FROM trades)''', (deposit_amount,))
    
    conn.commit()
    conn.close()

# 외부 출금 내역 기록 함수
def record_external_withdrawal(withdrawal_amount):
    conn = get_connection()
    c = conn.cursor()
    
    # 최신 거래 이후로 출금 금액을 기록 (DB에만 반영)
    c.execute('''UPDATE trades SET external_withdrawal = ? WHERE id = (SELECT MAX(id) FROM trades)''', (withdrawal_amount,))
    
    conn.commit()
    conn.close()

# 다음 DB 업데이트 시간을 계산하는 함수 (4시간마다 업데이트)
def get_next_update_time():
    now = datetime.now()
    # 4시간 단위 (00, 04, 08, 12, 16, 20) 중에서 가장 가까운 미래의 시간을 계산
    next_update_hour = (now.hour // 4 + 1) * 4
    if next_update_hour >= 24:
        next_update_hour = 0
        next_update = now.replace(day=now.day + 1, hour=next_update_hour, minute=0, second=0, microsecond=0)
    else:
        next_update = now.replace(hour=next_update_hour, minute=0, second=0, microsecond=0)
    
    return next_update

# 메인 함수
def main():
    st.title('Bitcoin GPT Auto Trading Dashboard')

    # 사용자로부터 추가 입금 및 출금 금액 입력 받기
    deposit_amount = st.number_input("추가 입금 금액 (KRW):", min_value=0, step=1000)
    if st.button("입금 기록"):
        record_external_deposit(deposit_amount)
        st.success(f'{deposit_amount} KRW 입금이 기록되었습니다. (다음 업데이트에 반영 예정)')

    withdrawal_amount = st.number_input("추가 출금 금액 (KRW):", min_value=0, step=1000)
    if st.button("출금 기록"):
        record_external_withdrawal(withdrawal_amount)
        st.success(f'{withdrawal_amount} KRW 출금이 기록되었습니다. (다음 업데이트에 반영 예정)')

    # 데이터 로드 (실시간 반영)
    df = load_data()

    if df.empty:
        st.warning('No trade data available.')
        return

    # 총 투자금 계산 (초기 투자금 + 추가 자금 - 출금)
    total_investment = calculate_total_investment(df)

    # 현재 자산 계산 (현금 + 비트코인 평가 자산, 추가금은 반영되지 않음)
    current_assets = calculate_current_assets(df)

    # 평가 수익 계산 (현재 자산 - 총 투자금)
    unrealized_profit = current_assets - total_investment
    unrealized_profit_rate = (unrealized_profit / total_investment) * 100 if total_investment > 0 else 0

    # 실현 수익 및 추가 자금 비교
    compare_profit_vs_funds(df)

    # 총 투자 금액(고정된 값) 출력
    st.header(f"💼 총 투자액 (고정): {total_investment:.0f} 원")
    st.header(f"💼 총 자산 (유동): {current_assets:.0f} 원")
    
    # 다음 업데이트 시점 계산
    next_update = get_next_update_time()
    st.info(f"다음 업데이트 시점: {next_update.strftime('%Y-%m-%d %H:%M:%S')}에 반영될 예정입니다.")

    # 실제 투자 금액(비트코인)과 현금 잔액 비율 계산
    invested_amount = calculate_invested_amount(df)
    current_krw_balance = df.iloc[-1]['krw_balance']

    # 원형 차트 데이터 준비
    labels = [
        f'현금 잔액: {current_krw_balance:,.0f} 원', 
        f'투자 중 (비트코인): {invested_amount:,.0f} 원'
    ]
    values = [current_krw_balance, invested_amount]

    # 원형 차트 출력
    st.header("🔄 현재 자산 분포")
    fig = px.pie(
        values=values, 
        names=labels, 
        title='현금과 투자 중인 자산 비율', 
        hole=0.3
    )

    # 금액도 표시하도록 설정
    fig.update_traces(textinfo='label+percent', hoverinfo='label+value', textposition='inside')
    st.plotly_chart(fig)

    # 수익률 출력
    st.header(f'📈 평가 수익률: {unrealized_profit_rate:.2f}%')
    st.write(f'평가 수익: {unrealized_profit:.0f} 원')

    # 기본 통계
    st.header('📊 Basic Statistics')
    st.write(f"총 거래 수: {len(df)}")
    st.write(f"첫 거래 날짜: {df['timestamp'].min()}")
    st.write(f"마지막 거래 날짜: {df['timestamp'].max()}")

    # 거래 내역 표시
    st.header('🧾 Trade History')
    st.dataframe(df)

    # 거래 결정 분포
    st.header('📊 Trade Decision Distribution')
    decision_counts = df['decision'].value_counts()
    if not decision_counts.empty:
        fig = px.pie(values=decision_counts.values, names=decision_counts.index, title='Trade Decisions')
        st.plotly_chart(fig)
    else:
        st.write("No trade decisions to display.")

    # BTC 잔액 변화
    st.header('BTC Balance Over Time')
    fig = px.line(df, x='timestamp', y='btc_balance', title='BTC Balance')
    st.plotly_chart(fig)

    # KRW 잔액 변화
    st.header('KRW Balance Over Time')
    fig = px.line(df, x='timestamp', y='krw_balance', title='KRW Balance')
    st.plotly_chart(fig)

    # BTC 평균 매수가 변화
    st.header('BTC Average Buy Price Over Time')
    fig = px.line(df, x='timestamp', y='btc_avg_buy_price', title='BTC Average Buy Price')
    st.plotly_chart(fig)

    # BTC 가격 변화
    st.header('BTC Price Over Time')
    fig = px.line(df, x='timestamp', y='btc_krw_price', title='BTC Price (KRW)')
    st.plotly_chart(fig)

if __name__ == "__main__":
    main()
