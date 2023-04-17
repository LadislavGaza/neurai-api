import score_batch
import json


dataset = ['/Users/lubomirdlhy/FIIT/TP/azure-model/mni152.nii']
score_batch.init()
res = score_batch.run(dataset)
print(res)