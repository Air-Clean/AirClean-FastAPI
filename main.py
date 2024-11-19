from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import csv
from prophet import Prophet
import os
import requests
import xmltodict
import json

app = FastAPI()

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인 허용. 실제 운영환경에서는 특정 도메인만 지정하세요
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# CSV 파일 읽기
file_path = './sales_data.csv'  # 적절한 파일 경로로 변경하세요.
data = pd.read_csv(file_path)

# 날짜 형식 변환
data['ds'] = pd.to_datetime(data['date'])
data['y'] = data['sales']

# Prophet 모델 준비 및 훈련
model = Prophet()

model.add_country_holidays(country_name='KR')
model.add_seasonality(name='monthly', period=30.5, fourier_order=5)

# 모델 훈련
model.fit(data[['ds', 'y']])

class Data(BaseModel):
    branch: int
    date: str
    sales: int



@app.post("/insert/data")
async def insert_data(request: Request):
    print("데이터 예측하기")
    
    try:
        data = await request.json()
        print("받은 데이터:", data['today'])

        current_dir = os.getcwd()
        file_path = os.path.join(current_dir, 'sales_data.csv')
        print(f"파일 경로: {file_path}")

        try:
            all_sales_data = pd.read_csv(file_path)
            print("파일 읽기 성공")
        except FileNotFoundError:
            print("파일이 없어서 새로 생성합니다")
            all_sales_data = pd.DataFrame(columns=['date', 'sales'])
        
        if not data or 'today' not in data or 'data' not in data or 'count' not in data:
            raise HTTPException(status_code=400, detail="필수 데이터가 누락되었습니다")
        
        print(1)
        # sales_data.csv 파일 읽기
        all_sales_data = pd.read_csv('./sales_data.csv')
        
        print(2)
        # 이번 달 데이터 업데이트
        today = pd.to_datetime(data['today'])
        start_of_month = today.replace(day=1)
        
        print(3)
        # today까지의 실제 데이터만 사용
        today_day = today.day  # 현재 일자 (19일)
        actual_data = data['data'][:today_day]  # 1일부터 today까지의 데이터만 사용
        
        print(4)
        dates = pd.date_range(start=start_of_month, periods=today_day, freq='D')
        
        print(5)
        # 새로운 데이터프레임 생성 (실제 데이터만)
        new_month_data = pd.DataFrame({
            'date': dates.strftime('%Y-%m-%d'),
            'sales': actual_data
        })
        print(6)
        
        # 기존 데이터에서 이번 달 데이터 제거
        all_sales_data = all_sales_data[~all_sales_data['date'].isin(new_month_data['date'])]
        print(7)
        
        # 새로운 데이터 추가
        all_sales_data = pd.concat([all_sales_data, new_month_data], ignore_index=True)
        print(8)
        # 날짜순으로 정렬
        all_sales_data['date'] = pd.to_datetime(all_sales_data['date'])
        all_sales_data = all_sales_data.sort_values('date')
        all_sales_data['date'] = all_sales_data['date'].dt.strftime('%Y-%m-%d')
        print(9)
        # 변경된 데이터를 CSV 파일에 저장
        # all_sales_data.to_csv('./sales_data.csv', index=False)

        try:
            print("파일 저장 시도...")
            all_sales_data.to_csv(file_path, index=False)
            print("파일 저장 성공")
        except Exception as e:
            print(f"파일 저장 실패: {str(e)}")

            
        print(10)
        # Prophet 모델 재학습
        model_data = all_sales_data.copy()
        model_data['ds'] = pd.to_datetime(model_data['date'])
        model_data['y'] = model_data['sales']
        
        global model
        model = Prophet()

        # 한국 공휴일 추가
        model.add_country_holidays(country_name='KR')

        # 월간 계절성 추가
        model.add_seasonality(
            name='monthly', 
            period=30.5, 
            fourier_order=5,  # 계절성의 복잡도
            mode='multiplicative'
        )

        # 주간 패턴 추가
        model.add_seasonality(
            name='weekly',
            period=7,
            fourier_order=3,
            mode='multiplicative'
        )

        # 이상치 제거 (예: 매출이 0인 날 또는 비정상적으로 높은 날)
        model_data = model_data[
            (model_data['y'] > 0) & 
            (model_data['y'] < model_data['y'].quantile(0.99))  # 상위 1% 제외
        ]

        print("모델 피팅 시작...")
        model.fit(model_data[['ds', 'y']])
        print("모델 학습 완료")

        # 예측 수행
        future = model.make_future_dataframe(periods=data['count'])
        
        # 주말 효과 반영
        future['weekend'] = future['ds'].dt.dayofweek.isin([5, 6]).astype(int)
        
        forecast = model.predict(future)
        
        # 예측값 후처리
        forecast_data = forecast.tail(data['count']).copy()
        forecast_data['yhat'] = forecast_data['yhat'].clip(lower=0)  # 음수 제거
        
        # 이동평균을 사용한 스무딩
        forecast_data['yhat'] = forecast_data['yhat'].rolling(window=3, min_periods=1, center=True).mean()
        
        # 최종 예측값 반올림
        forecast_data['yhat'] = forecast_data['yhat'].round().astype(int)
        
        # 신뢰구간도 같이 처리
        forecast_data['yhat_lower'] = forecast_data['yhat_lower'].clip(lower=0).round().astype(int)
        forecast_data['yhat_upper'] = forecast_data['yhat_upper'].clip(lower=0).round().astype(int)

        # 결과 반환
        predicted_sales = forecast_data['yhat'].tolist()
        
        return {"message": "데이터 삽입 성공", "code": 200, "data": predicted_sales}
        
    except Exception as e:
        print(f"에러 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"데이터 삽입 실패: {str(e)}")


@app.get("/predictAll")
def predict(days: int):
    future = model.make_future_dataframe(periods=days)
    forecast = model.predict(future)
    forecast = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
    return forecast.tail(days).to_dict('records')

@app.post("/sales/insert")
async def insert_data(data: Data):

    data_dict = data.dict()
    file_path = f'./branch/Branch_{data_dict["branch"]}_sales_data.csv'

    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    try:
        branch_sales_data = pd.read_csv(file_path)
        if data_dict['date'] in branch_sales_data['date'].values:
            # 그 값을 현재값을 더해서 업데이트 해줌
            all_sales_data = pd.read_csv('./sales_data.csv')
            all_sales_data.loc[all_sales_data['date'] == data_dict['date'], 'sales'] -= branch_sales_data.loc[branch_sales_data['date'] == data_dict['date'], 'sales']
            branch_sales_data.loc[branch_sales_data['date'] == data_dict['date'], 'sales'] = data_dict['sales']
            print(branch_sales_data.loc[branch_sales_data['date'] == data_dict['date'], 'sales'])
            all_sales_data['sales'] = all_sales_data['sales'].astype(int)
            all_sales_data.to_csv('sales_data.csv', index=False)
        else:
            # 존재하지 않는다면 초기값으로 설정 후 값을 insert
            new_data = pd.DataFrame([[data_dict['date'], data_dict['sales']]], columns=['date', 'sales'])
            branch_sales_data = pd.concat([branch_sales_data, new_data], ignore_index=True)
        # 업데이트 된 csv 파일을 덮어쓰기
        branch_sales_data.to_csv(file_path, index=False)
        # with open(file_path, 'a', encoding='utf-8', newline='') as f:
        #     wr = csv.writer(f)
        #     wr.writerow([data_dict['date'], data_dict['sales']])
        # file_path = f'./sales_data.csv'


        # 총매출 파일 열기
        all_sales_data = pd.read_csv('./sales_data.csv')

        # 만약에 모든 지점 파일안에 date 가 이미 존재한다면
        if data_dict['date'] in all_sales_data['date'].values:
            # 그 값을 현재값을 더해서 업데이트 해줌
            all_sales_data.loc[all_sales_data['date'] == data_dict['date'], 'sales'] += data_dict['sales']
        else:
            # 존재하지 않는다면 초기값으로 설정 후 값을 insert
            new_data = pd.DataFrame([[data_dict['date'], data_dict['sales']]], columns=['date', 'sales'])
            all_sales_data = pd.concat([all_sales_data, new_data], ignore_index=True)
        # 업데이트 된 csv 파일을 덮어쓰기
        all_sales_data.to_csv('sales_data.csv', index=False)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write data to file: {str(e)}")

    return {"message": "Data inserted successfully"}


@app.get("/water/quality")
def getWaterQuality(site_id: str):
    url = 'http://openapi.seoul.go.kr:8088/sample/xml/WPOSInformationTime/1/5/'
    response = requests.get(url)
    
    
    if response.status_code == 200:
        response.encoding = 'utf-8'
        data = xmltodict.parse(response.content)
        rows = data.get("WPOSInformationTime", {}).get("row", [])
        filtered_data = [row for row in rows if row.get("SITE_ID") == site_id]
        if filtered_data:
            evaluated_data = [evaluate_water_quality(row) for row in filtered_data]
            return evaluated_data
        else:
            return {"message": "No data found for the given site_id"}
    else:
        return {"error": "Failed to fetch data from API"}
    
def evaluate_water_quality(data):
    evaluation = {}

    # Evaluate temperature
    if float(data['W_TEMP']) < 20:
        evaluation['W_TEMP'] = '양호'
    elif 20 <= float(data['W_TEMP']) < 30:
        evaluation['W_TEMP'] = '보통'
    else:
        evaluation['W_TEMP'] = '나쁨'

    # Evaluate pH
    if 6.5 <= float(data['W_PH']) <= 8.5:
        evaluation['W_PH'] = '양호'
    elif 5.5 <= float(data['W_PH']) < 6.5 or 8.5 < float(data['W_PH']) <= 9.5:
        evaluation['W_PH'] = '보통'
    else:
        evaluation['W_PH'] = '나쁨'

    # Evaluate dissolved oxygen
    if float(data['W_DO']) >= 5:
        evaluation['W_DO'] = '양호'
    elif 3 <= float(data['W_DO']) < 5:
        evaluation['W_DO'] = '보통'
    else:
        evaluation['W_DO'] = '나쁨'

    # Evaluate total nitrogen
    if float(data['W_TN']) < 1:
        evaluation['W_TN'] = '양호'
    elif 1 <= float(data['W_TN']) < 3:
        evaluation['W_TN'] = '보통'
    else:
        evaluation['W_TN'] = '나쁨'

    # Evaluate total phosphorus
    if float(data['W_TP']) < 0.1:
        evaluation['W_TP'] = '양호'
    elif 0.1 <= float(data['W_TP']) < 0.3:
        evaluation['W_TP'] = '보통'
    else:
        evaluation['W_TP'] = '나쁨'

    # Evaluate total organic carbon
    if data['W_TOC'] is not None:
        if float(data['W_TOC']) < 3:
            evaluation['W_TOC'] = '양호'
        elif 3 <= float(data['W_TOC']) < 6:
            evaluation['W_TOC'] = '보통'
        else:
            evaluation['W_TOC'] = '나쁨'
    else:
        evaluation['W_TOC'] = '데이터 없음'

    # Evaluate phenol
    if float(data['W_PHEN']) < 0.005:
        evaluation['W_PHEN'] = '양호'
    elif 0.005 <= float(data['W_PHEN']) < 0.01:
        evaluation['W_PHEN'] = '보통'
    else:
        evaluation['W_PHEN'] = '나쁨'

    # Evaluate cyanide
    if float(data['W_CN']) < 0.005:
        evaluation['W_CN'] = '양호'
    elif 0.005 <= float(data['W_CN']) < 0.01:
        evaluation['W_CN'] = '보통'
    else:
        evaluation['W_CN'] = '나쁨'

    return evaluation


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)




