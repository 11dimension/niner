import pymongo

mongodb_client = pymongo.MongoClient(host='127.0.0.1', port=27017)
mongodb_client['deployment'].authenticate('niner', '123456')


rst = mongodb_client['deployment']['account'].find_one({
    "username": 'sunyifan',
    "password": 'a7fbf7f76b44f814606099d7acf9b9fb'
})

print(rst)
