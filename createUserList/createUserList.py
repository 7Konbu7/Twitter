 
from requests_oauthlib import OAuth1Session
import datetime,time,sys,json
from abc import ABCMeta, abstractmethod
 
CK = ""   # Consumer Key
CS = ""   # Consumer Secret
AT = ""   # Access Token
AS = ""   # Accesss Token Secert
 
class TweetsGetter(object):
    __metaclass__ = ABCMeta
 
    def __init__(self):
        self.session = OAuth1Session(CK, CS, AT, AS)
 
    @abstractmethod
    def specifyUrlAndParams(self, keyword):
        '''
        呼出し先 URL、パラメータを返す
        '''
 
    @abstractmethod
    def pickupTweet(self, res_text, includeRetweet):
        '''
        res_text からツイートを取り出し、配列にセットして返却
        '''
 
    @abstractmethod
    def getLimitContext(self, res_text):
        '''
        回数制限の情報を取得 （起動時）
        '''
 
    def collect(self, total = -1, onlyText = False, includeRetweet = False):
        '''
        ツイート取得を開始する
        '''
 
        #----------------
        # 回数制限を確認
        #----------------
        self.checkLimit()
 
        #----------------
        # URL、パラメータ
        #----------------
        url, params = self.specifyUrlAndParams()
        params['include_rts'] = str(includeRetweet).lower()
        # include_rts は statuses/user_timeline のパラメータ。search/tweets には無効
 
        #----------------
        # ツイート取得
        #----------------
        cnt = 0
        unavailableCnt = 0
        while True:
            res = self.session.get(url, params = params)
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
 
            tweets = self.pickupTweet(json.loads(res.text))
            if len(tweets) == 0:
                # len(tweets) != params['count'] としたいが
                # count は最大値らしいので判定に使えない。
                # ⇒  "== 0" にする
                # https://dev.twitter.com/discussions/7513
                break
 
            for tweet in tweets:
                if (('retweeted_status' in tweet) and (includeRetweet is False)):
                    pass
                else:
                    if onlyText is True:
                        yield tweet['text']
                    else:
                        yield tweet
 
                    cnt += 1
                    if cnt % 100 == 0:
                        print ('%d件 ' % cnt)
 
                    if total > 0 and cnt >= total:
                        return
 
            params['max_id'] = tweet['id'] - 1
 
            # ヘッダ確認 （回数制限）
            # X-Rate-Limit-Remaining が入ってないことが稀にあるのでチェック
            if ('X-Rate-Limit-Remaining' in res.headers and 'X-Rate-Limit-Reset' in res.headers):
                if (int(res.headers['X-Rate-Limit-Remaining']) == 0):
                    self.waitUntilReset(int(res.headers['X-Rate-Limit-Reset']))
                    self.checkLimit()
            else:
                print ('not found  -  X-Rate-Limit-Remaining or X-Rate-Limit-Reset')
                self.checkLimit()
 
    def checkLimit(self):
        '''
        回数制限を問合せ、アクセス可能になるまで wait する
        '''
        unavailableCnt = 0
        while True:
            url = "https://api.twitter.com/1.1/application/rate_limit_status.json"
            res = self.session.get(url)
 
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
 
    @staticmethod
    def bySearch(keyword):
        return TweetsGetterBySearch(keyword)
 
class TweetsGetterBySearch(TweetsGetter):
    '''
    キーワードでツイートを検索
    '''
    def __init__(self, keyword):
        super(TweetsGetterBySearch, self).__init__()
        self.keyword = keyword
        
    def specifyUrlAndParams(self):
        '''
        呼出し先 URL、パラメータを返す
        '''
        url = 'https://api.twitter.com/1.1/search/tweets.json'
        params = {'q':self.keyword, 'count':100}
        return url, params
 
    def pickupTweet(self, res_text):
        '''
        res_text からツイートを取り出し、配列にセットして返却
        '''
        results = []
        for tweet in res_text['statuses']:
            results.append(tweet)
 
        return results
 
    def getLimitContext(self, res_text):
        '''
        回数制限の情報を取得 （起動時）
        '''
        remaining = res_text['resources']['search']['/search/tweets']['remaining']
        reset     = res_text['resources']['search']['/search/tweets']['reset']
 
        return int(remaining), int(reset)
    
if __name__ == '__main__':
 
    info = {}
    # キーワードで取得
    getter = TweetsGetter.bySearch("XXX")
    cnt = 0
    for tweets in getter.collect(total = 100):
        cnt += 1
        if "Screen" not in info:
            info["Screen"] = []
        # 好きな条件で
        follower = tweets['user']['followers_count']
        if 500 <= follower <= 1000:
            # 下ネタ系アカウントを適当に回避
            if "風俗" in tweets['text']:
                continue
            if "おっぱい" in tweets['text']:
                continue
            if "エロ" in tweets['text']:
                continue
            if "セフレ" in tweets['text']:
                continue
            if "童貞" in tweets['text']:
                continue
            if "デリヘル" in tweets['text']:
                continue
            if "風俗" in tweets['user']['name']:
                continue
            info["Screen"].append(tweets['user']['screen_name'])
            contents = info["Screen"]
            contents.append({"User":""})
            content = contents[-1]
            content["User"] = tweets['user']['name']
            content["UserID"] = tweets['user']['id_str']
            content["Follower"] = follower
            content["tweet"] = tweets['text']
            print ('------ %d' % cnt)
            print ('{} {} {}'.format(tweets['id'], tweets['created_at'], '@'+tweets['user']['screen_name']))
            print (tweets['text'])
    with open("userList.json", "w") as fh:
        json.dump(info,fh,indent=4,ensure_ascii=False)
