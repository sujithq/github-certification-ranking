import requests, json
u='sujith'
data=requests.get(f'https://www.credly.com/users/{u}/badges.json?page=1&per_page=100',timeout=20).json()
ids={}
for b in data.get('data',[]):
    for e in b.get('issuer',{}).get('entities',[]):
        ent=e.get('entity',{})
        i=ent.get('id'); n=ent.get('name')
        if i: ids[i]=n
for i,n in sorted(ids.items(), key=lambda x:(x[1] or '', x[0])):
    print(f'{i} | {n}')