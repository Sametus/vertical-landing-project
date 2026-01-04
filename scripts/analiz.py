import pandas as pd
import plotly.express as px

df = pd.read_csv("models/detailed_log.csv")

print(df.head())

df_success = df[df["Return"] == "Success"]
df_success = df_success.reset_index()
print(df_success.head())
print("*****************")
print(df.shape)
print("*********************")
#px.line(data_frame=df_success, x=df_success.index, y = df_success["StartAlt"]).show()
df = df.reset_index(drop="index")
print(df.loc[0:50])

for i in range(0,df.shape[0]):
    if i % 50 == 0:
        print(df.loc[i-50:i,['Return','StartAlt']].groupby('Return').mean())
#px.line(data_frame=means, x=range(0,len(means)), y = means).show()