from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import csv
from prophet import Prophet
import os

app = FastAPI()

# CSV 파일 읽기
file_path = './sales_data.csv'  # 적절한 파일 경로로 변경하세요.
data = pd.read_csv(file_path)

# 날짜 형식 변환
data['ds'] = pd.to_datetime(data['date'])
data['y'] = data['sales']

# Prophet 모델 준비 및 훈련
model = Prophet()
model.fit(data[['ds', 'y']])

class Data(BaseModel):
    branch: int
    date: str
    sales: int

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
