import os, json
from tqdm import tqdm
def proc(day, candidate):
    of = open('data-%s/%s.jsonl' % (day, candidate), 'w+')
    bp = 'data-%s/%s/' % (day, candidate)
    lst = os.listdir(bp)
    print('%d files in %s' % (len(lst), bp))
    for fp in tqdm(lst):
        with open(os.path.join(bp, fp), 'r') as f:
            data = json.load(f)
            of.write(json.dumps(data))
            of.write('\n')
    of.close()

def proc_all(day):
    for candidate in os.listdir('data-%s/' % day):
        proc(day, candidate)
