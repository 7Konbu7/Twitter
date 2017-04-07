
from requests_oauthlib import OAuth1Session
import json,time,datetime,sys,os
import queue,threading


class CreateFollowList():

    def __init__(self,consumer_key,consumer_secret,access_token,access_token_secret, screen_name_queue):
        """
        Oath認証まわり
        """
        self.oath = OAuth1Session(consumer_key,consumer_secret,access_token,access_token_secret)
        self.screen_name_queue = screen_name_queue
        self.lock = threading.Lock()

    def limit_notification(self,res,method):
        """
        使用するAPIのアクセス可能回数とリセット時間を表示する
        """
        print ('{}のアクセス可能回数:{}'.format(method,res.headers['X-Rate-Limit-Remaining']))
        #print ('リセット時間:{}'.format(res.headers['X-Rate-Limit-Reset']))
        sec = int(res.headers['X-Rate-Limit-Reset'])\
                    - time.mktime(datetime.datetime.now().timetuple())
        print ('リセット時間:{}秒'.format(sec))
        print ('リセット時間:{}分'.format(int(sec/60)))

    def getLimitContext(self, res_text):
        '''
        回数制限の情報を取得 （起動時）
        '''
        remaining = res_text['resources']['search']['/search/tweets']['remaining']
        reset     = res_text['resources']['search']['/search/tweets']['reset']
 
        return int(remaining), int(reset)


    def checkLimit(self):
        '''
        回数制限を問合せ、アクセス可能になるまで wait する
        '''
        unavailableCnt = 0
        while True:
            url = "https://api.twitter.com/1.1/application/rate_limit_status.json"
            res = self.oath.get(url)
 
            if res.status_code == 503:
                # 503 : Service Unavailable
                if unavailableCnt > 10:
                    raise Exception('Twitter API error %d' % res.status_code)
 
                unavailableCnt += 1
                print ('Service Unavailable 503')
                self.waitUntilReset(time.mktime(datetime.datetime.now().timetuple()) + 30)
                continue
 
            unavailableCnt = 0
 
            if res.status_code != 200:
                raise Exception('Twitter API error %d' % res.status_code)
 
            remaining, reset = self.getLimitContext(json.loads(res.text))
            if (remaining == 0):
                self.waitUntilReset(reset)
            else:
                break

    def waitUntilReset(self, reset):
        '''
        reset 時刻まで sleep
        '''
        seconds = reset - time.mktime(datetime.datetime.now().timetuple())
        seconds = max(seconds, 0)
        print ('\n     =====================')
        print ('     == waiting %d sec ==' % seconds)
        print ('     =====================')
        sys.stdout.flush()
        time.sleep(seconds + 10)  # 念のため + 10 秒


    def worker(self, count=200):
        """
        main処理    
        """
        fetched_screen_names = []

        while True:
            screen_name = self.screen_name_queue.get()
            print("UserName: {}".format(screen_name))
            if screen_name is None:
                print("Queue is empty")
                break

            cursor = -1
            # cursorが0になったときがフォロワー全員取得完了のサイン
            while cursor != 0:
                url = "https://api.twitter.com/1.1/followers/list.json"
                params = {
                    "screen_name": "{}".format(screen_name),
                    "count": "{}".format(count),
                    "cursor": "{}".format(cursor)
                    }
                response = self.oath.get(url, params = params)
                result = json.loads(response.text)
                # ヘッダ確認 （回数制限）
                # X-Rate-Limit-Remaining が入ってないことが稀にあるのでチェック
                if ('X-Rate-Limit-Remaining' in response.headers and 'X-Rate-Limit-Reset' in response.headers):
                    self.limit_notification(response,"Extract_follower")
                    if (int(response.headers['X-Rate-Limit-Remaining']) == 0):
                        self.waitUntilReset(int(response.headers['X-Rate-Limit-Reset']))
                        self.checkLimit()
                else:
                    print ('not found  -  X-Rate-Limit-Remaining or X-Rate-Limit-Reset')
                    self.checkLimit()
                try:
                    cursor = result["next_cursor"]
                except KeyError:
                    break

                fetched_screen_names += [x["screen_name"] for x in result["users"] if not x["protected"]]

            try:
                with open("to_follow.json", "r") as fh:
                    saved_screen_names = list(set(json.load(fh)))
            except FileNotFoundError:
                saved_screen_names = []
            
            saved_screen_names += fetched_screen_names
            with self.lock:
                with open("to_follow.json", "w") as fh:
                    json.dump(saved_screen_names, fh, indent=4, ensure_ascii=False)
            print ("cursor: {}".format(cursor))
            self.screen_name_queue.task_done()


### Execute                                                                                                                                                       
if __name__ == "__main__":
    screen_name_queue = queue.Queue()
    
    keys = [
        # nae
        [
            "",
            "",
            "",
            "",
        # mayuri
        ],[
            "",
            "",
            "",
            "",
        ]

    ]
    instances = [CreateFollowList(*key, screen_name_queue) for key in keys]

    # 予め生成された対象ユーザリストの読み込み
    # これらのユーザのフォロワーをフォローしていく
    with open("userList.json","r") as fh:
        users = json.load(fh)

    # 対象ユーザのスクリーンネームとUserIDをそれぞれ辞書化
    screen_names = [users['Screen'][i] for i in range(0, len(users['Screen']), 2)]
    for screen_name in screen_names:
        screen_name_queue.put(screen_name)

    threads = []
    for instance in instances:
        t = threading.Thread(target=instance.worker)
        t.start()
        threads.append(t)
    screen_name_queue.join()

    for _ in range(len(threads)):
        screen_name_queue.put(None)

    for t in threads:
        t.join()
    
