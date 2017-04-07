

from requests_oauthlib import OAuth1Session
import json,time,datetime,os


class AutoRemove():

    def __init__(self,consumer_key,consumer_secret,access_token,access_token_secret):
        """
        Oath認証まわり
        """
        self.oath = OAuth1Session(consumer_key,consumer_secret,access_token,access_token_secret)

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

    def limit_notification(self,res,method):
        """
        使用するAPIのアクセス可能回数とリセット時間を表示する
        """
        print ('{}のアクセス可能回数:{}'.format(method,res.headers['X-Rate-Limit-Remaining']))
        print ('リセット時間:{}'.format(res.headers['X-Rate-Limit-Reset']))
        sec = int(res.headers['X-Rate-Limit-Reset'])\
                    - time.mktime(datetime.datetime.now().timetuple())
        print ('リセット時間:{}秒'.format(sec))
        print ('リセット時間:{}分'.format(int(sec/60)))

    def extract_follow(self,user_id,screen_name,count):
        """
        指定ユーザのフォローユーザを辞書で返す。
        しかし、cursorには関与していないので最大で100人前後が限界

        :param result(dictionary): following list of the user
        """
        url = "https://api.twitter.com/1.1/friends/list.json"
        params = {
            "user_id": "{}".format(user_id),
            "screen_name": "{}".format(screen_name),
            "count": "{}".format(count)
            }
        response = self.oath.get(url, params = params)
        if ('X-Rate-Limit-Remaining' in response.headers and 'X-Rate-Limit-Reset' in response.headers):
            self.limit_notification(response,"Extract_follower")
            if (int(response.headers['X-Rate-Limit-Remaining']) == 0):
                self.waitUntilReset(int(response.headers['X-Rate-Limit-Reset']))
                self.checkLimit()
            else:
                print ('not found  -  X-Rate-Limit-Remaining or X-Rate-Limit-Reset')
                self.checkLimit()
        if response.status_code != 200:
            print ("Error code:{}".format(response.status_code))
            return None
        #return response.text
        result = json.loads(response.text)
        return result


    def remove(self):
        """
        ユーザを指定後、そのユーザのフォロワーを任意の数までリムーブする
        基本的には自身を指定する。
        cursorの設定はしていないので100人前後が限界
        """
        url = "https://api.twitter.com/1.1/friendships/destroy.json"
        cnt = 0
        to_remove = []
        # userID,screenName,試行回数をそれぞれ入力
        result = self.extract_follow("741920978091937792","12test_test34","100")
        for order in range(len(result["users"])):
            to_remove.append((result["users"][order]["screen_name"]))
        to_remove.reverse()
        #print ("フォロワー:{}".format(to_remove))
        for order in range(len(to_remove)):
            url = "https://api.twitter.com/1.1/friendships/show.json"
            params = {
                "source_screen_name": "{}".format("12test_test34"),
                "target_screen_name": "{}".format(to_remove[order])
                }
            # POSTは常識の範囲内でいくらでもやっていいらしい
            response = self.oath.get(url, params = params)
            if ('X-Rate-Limit-Remaining' in response.headers and 'X-Rate-Limit-Reset' in response.headers):
                self.limit_notification(response,"Show_Friendships")
                if (int(response.headers['X-Rate-Limit-Remaining']) == 0):
                    self.waitUntilReset(int(response.headers['X-Rate-Limit-Reset']))
                    self.checkLimit()
                else:
                    print ('not found  -  X-Rate-Limit-Remaining or X-Rate-Limit-Reset')
                    self.checkLimit()
            if response.status_code != 200:
                print ("Error code:{}".format(response.status_code))
                return None
            result = json.loads(response.text)
            if result["relationship"]["source"]["followed_by"] == False:
                print ("{}からのフォロー: {}".format(to_remove[order],result["relationship"]["source"]["followed_by"]))
                url = "https://api.twitter.com/1.1/friendships/destroy.json"
                params = {
                    "screen_name": "{}".format(to_remove[order])
                    }
                response = self.oath.post(url, params = params)
                print ("ScreenName {}: {}".format(to_remove[order],response.status_code))
                if response.status_code != 200:
                    print ("failed removing")
                else:
                    cnt = cnt + 1
        print ("リムーブ成功数: {}".format(cnt))

### Execute                                                                                                                                                       
if __name__ == "__main__":
    exe = AutoFollowRemove(
    "",
    "",
    "",
    ""
    )
    exe.remove()

