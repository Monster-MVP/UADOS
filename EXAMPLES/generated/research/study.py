import csv, json, random
from statistics import mean
random.seed(7)
with open('dataset.csv', newline='') as stream:
    values = [float(row['value']) for row in csv.DictReader(stream)]
print(json.dumps({'mean': mean(values), 'n': len(values), 'seed': 7}))
