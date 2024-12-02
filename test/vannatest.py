from vanna.remote import VannaDefault
vn = VannaDefault(model='test2820', api_key='6b837c6bf630461eab556b4223ed8c22')
vn.connect_to_postgres(host='222.20.96.38', dbname='SiemensHarden_DB', user='postgres', password='Liu_123456', port='5432')
training_data = vn.get_training_data()
print("------------------------------------training_data-------------------------------------")
print(training_data)
answer=vn.ask('Find 10 siemens_advisories data')
str,data,figure=answer
