import os 

path = os.path.dirname(os.path.realpath(__file__))

with open(path + '/sample.txt', 'r') as file:
    sample = file.read()

if os.path.exists(path + '/count.txt') == False:
    with open(path + '/count.txt', 'w') as file:
        file.write("")

with open(path + '/count.txt', 'r') as file:
    count = file.read()

sample_list = sample.split(' ')
sample_index = sample_list.index('[?]')
count_list = count.split(' ')

if len(sample_list) == len(count_list):
    sample_test = sample_list.copy()
    sample_test.pop(sample_index)
    count_test = count_list.copy()
    count_test.pop(sample_index)
else:
    sample_test = sample_list.copy()
    sample_test.pop(sample_index)
    count_test = None

if sample_test == count_test:
    count_number = int(count_list[sample_index])
    count_number += 1
    sample_list[sample_index] = str(count_number)
else:
    sample_list[sample_index] = str(0)

count = ' '.join(sample_list)
with open(path + '/count.txt', 'w') as file:
    file.write(count)