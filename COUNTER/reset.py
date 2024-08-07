import os

path = os.path.dirname(os.path.realpath(__file__))

if os.path.exists(path + '/count.txt') == True:
    os.remove(path + '/count.txt')

os.system(path + '/counter.py')