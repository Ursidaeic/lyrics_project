import json, requests, time, random, re, textdistance, threading, os
from queue import Queue
from bs4 import BeautifulSoup
from tqdm import tqdm

path = "forlang_song_identifier/data/"

def dump_func(filename, obj):
    with open(f"{path}{filename}.json", "w", encoding="utf8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=0)
    

def get_func(url, sleep_range):
    sleep_range = [5,10]
    header = {'User-Agent': 'Lyrics language checker'}
    r = requests.get(url, headers = header)
    if r.status_code != 200:
        print(f"\n{r.status_code} from {url}")
        return 0
    else:
        time.sleep(random.uniform(sleep_range[0], sleep_range[1]))
        return r


def formatter(text):
    #common words that confuse the lang detection software
    stopwords = set(("oh", "eh","la", "ha", "hallelujah", "ah", "ooh"))
    text = re.findall(r'\w+\'?\w+\n?', text)

    newtext = [word for word in text if not word.strip("\n") in stopwords]
    newtext = " ".join(newtext)
    
    for cha in newtext:
        if cha in bads:
            text = text.replace(cha,'')
    return newtext
            
def checklang(song, lyrics):
    lyrics = formatter(lyrics)
    
    try:
        isReliable, textBytesFound, details = cld2.detect(lyrics)
        
    except ValueError as e:
        errors.append(song)
        with open(path+"errors.json", "w", encoding="utf-8") as f:
            json.dump(errors, f, ensure_ascii=False)
        return
    
    language = re.search("ENGLISH", str(details))
    if language == None:
        foreignlang.append(song)
        with open(path+"foreignlang.json", "w", encoding="utf-8") as f:
            json.dump(foreignlang, f)

    if len(re.findall("Unknown", str(details))) < 2:
        foreignlang.append(song)
        with open(path+"foreignlang.json", "w", encoding="utf-8") as f:
            json.dump(foreignlang, f)
            
    #============================================================#
def az_artist_searcher(artist):
    encoded_artist = re.sub(r"\s", "+", artist)
    #search for an artist on AZ lyrics
    url = f"https://search.azlyrics.com/search.php?q={encoded_artist}"
    r = get_func(url, (20, 30))
    soup = BeautifulSoup(r.text, 'html.parser')
    
    if not re.search("Artist results", r.text):
        return 0
    
    link_list = []
    for item in soup.select('div'):
        if item.attrs == {'class': ['panel']}:
            if item.contents[1].find('b').get_text() == "Artist results:":
                for link in item.find_all('a'):
                    if "https" in str(link):
                        link_list.append(link.get('href'))
                        
    #picks the result which most closely matches the queried artist (or the only result if there is only 1)
    if len(link_list) == 1:
        link = link_list[0]
        r = get_func(link, (20, 30))
        soup = BeautifulSoup(r.text, 'html.parser') 
        
    else:
        for i, link in enumerate(link_list):
            l = link.split("/")
            art = l[len(l)-1][:-5]
            jaro = textdistance.jaro_winkler(re.sub(r"\s", "", artist), art)
            link_list[i] = (jaro, link)
        link_list.sort()

        url = link_list[-1][1]
        r = get_func(url, (20, 30))
        soup = BeautifulSoup(r.text, 'html.parser')
    
    #finds and returns the full list of songs present on AZlyrics with corresponding link to lyrics page
    songs_dict = {}
    for link in soup.find_all('a'):
        l = link.get('href')
        if l:
            if "/lyrics/" in l:
                if ".." in l:
                    l  = "https://www.azlyrics.com/" + l[2:]
                    songs_dict.update({link.get_text().lower(): l})
                else:
                    songs_dict.update({link.get_text().lower(): l})

    
    return songs_dict



def az_song_searcher(song):
    artists = song['artists']
    title = song['title']
    ### copy some logic from the other for artists loop
    for artist in artists:
        song = "+".join(song)
        song = re.sub(r"\s", "+", song)
        r = get_func(f"https://search.azlyrics.com/search.php?q={song}&x=62ea26e9d8f4fb60ae9f8e35bc3ee3feb516419c1b5e2f1d62061d6238d0acb3", (10, 20))
    
        if r == 0:
            return 0
        if not re.search("Song results", r.text):
            with open ("lyric.txt", "w") as f:
                f.write(r.text)
            return 0
        else:
            soup = BeautifulSoup(r.text, 'html.parser') 
            link_list = []
            for item in soup.select('div'):
                if item.attrs == {'class': ['panel']}:
                    if item.contents[1].find('b').get_text() == "Song results:":
                        for link in item.find_all('a'):
                            if "https" in str(link):
                                link_list.append(link.get('href'))
    
        for link in link_list:
            ll = link.split("/")
            print(ll)
            print(re.sub(r"\s", "", artist), ll[4])
            art = textdistance.jaro_winkler(re.sub(r"\s", "", artist), ll[4])
            tit = textdistance.jaro_winkler(re.sub(r"\s", "", title), ll[5][:-5])
            if art and tit > 0.8:
                return get_az_lyrics(link)
            else:
                return 0

def get_az_lyrics(url):
    r = get_func(url, (10, 20))
    if r == 0:
        return 0
    soup = BeautifulSoup(r.text, 'html.parser')
    l = soup.find_all("div", attrs={"class": None, "id": None})
    if not l:
        return 0
    elif l:
        l = [x.getText() for x in l]
        return l
    
def az():
    while q.empty() == False:
        song = q.get()
        lyrics = az_song_searcher(song)
        if lyrics == 0:
            pass
        else:
            checklang(song, lyrics[0])
            
        
        qlist=[item for item in q.queue]
            
    #============================================================#

    
def lcom_searcher(artist):
    artist = re.sub(r"\s", "+", artist)
    r = get_func(f"https://www.lyrics.com/serp.php?st={artist}", (2, 4))
    if r == 0:
        return 0
    artist_found = False
    soup = BeautifulSoup(r.text, 'html.parser')
    for item in soup.find_all("tr"):
        for link in item.find_all('a'):
            l = link.get_text()
            if textdistance.jaro_winkler(link.get_text().lower(), artist) >= 0.9:
                if "sub-artist" not in link.get('href'):
                    artist_link = f"https://www.lyrics.com/{link.get('href')}"
                    adata = get_func(artist_link, (2,4))
                    if r == 0:
                        return 0
                    artist_found = True
                    return adata
                    
    
    if artist_found == False:
        return 0
    
def lcom_lyrics(url):
    ldata = get_func(url, (2, 4))
    if ldata == 0:
        return 0
    soup = BeautifulSoup(ldata.text, 'html.parser')
    for item in soup.select("pre"):
        lyrics = item.get_text()
        return(lyrics)
    
def lcom_artist_searcher(artist):
    adata = lcom_searcher(artist)
    if adata == 0:
        return 0
    
    else:
        song_list = []
        soup = BeautifulSoup(adata.text, 'html.parser')
        for link in soup.find_all('a'):
            try:
                if "/lyric/" in link.get('href'):
                    song_list.append([link.get_text().lower(), f"https://www.lyrics.com/{link.get('href')}"])
            except TypeError:
                pass
        
        return song_list           

if __name__ == '__main__':
    #============================================================#
    #set of characters cld2 is unable to process
    bads = set()
    for i in range(100000):
        try:
            sentence = f"try {chr(i)} it"

            cld2.detect(sentence)
        except:
            bads.add(chr(i))
    
    #============================================================#
    #Load existing data from files
    q = Queue()
    try:
        with open(path+"queue.json", "r", encoding="utf-8") as f:
            init_qlist = json.load(f)
            for item in init_qlist:
                q.put(item)
    except:
        pass
    
        
    with open(path+"unique.json", "r", encoding="utf-8") as f:
        entries = json.load(f)
    try:
        with open (path+"errors.json", "r", encoding="utf-8") as f:
            errors = json.load(f)
            
    except:
        errors = []
    
    try:
        with open (path+"foreignlang.json", "r", encoding="utf-8") as f:
            foreignlang = json.load(f)
    except:
        foreignlang = []
    
    #============================================================#
    #Create song lists etc.
    test = [] 
    art_list = []
    for item in entries:
        art_list.append(item[0])
    
    #============================================================#
    songs = entries
    

    thread = threading.Thread(target=az, args=())

    
    string = f"{len(errors)} errors. {len(foreignlang)} foreign lang songs. {q.qsize()} songs in queue"
    pbar = tqdm(total=len(songs), desc=string)

    
    #while there are still songs in list:
    while len(songs) != 0:
        song = songs[0]
        artist = song[0]
        title = song[1]
        count = art_list.count(artist)
        
        #retrieve list of songs by that artist
        song_list = lcom_artist_searcher(artist)
        
        
        # if that artist not found on lyrics.com, pass it on to azlyrics
        if song_list == 0:
            for i in range(count):
                q.put(songs[i])
            
            if not thread.is_alive():
                thread = threading.Thread(target=az, args=())
                thread.start()
                
            songs = songs[count:]
            
            

        #otherwise,
        else:
            for i in range(count):
                s = songs[i]
                match = False

                for item in song_list:
                    #attempts to match to a song from the retrieved song list 
                    if textdistance.jaro_winkler(s[1], item[0]) >= 0.9:
                        match = True

                        lyrics = lcom_lyrics(item[1])
                        #If the page is empty of lyrics put in AZlyrics queue
                        if lyrics == None:
                            q.put(s)
                            break
                        #If another exception is raised (HTTP error), put it in queue
                        if lyrics == 0:
                            q.put(s)
                            break
                        checklang(s, lyrics)
                        
                        pbar.set_description(f"{len(errors)} errors. {len(foreignlang)} foreign lang songs. {q.qsize()} songs in queue", refresh=True)     
                        pbar.update(1)
                        break

                    #if no match for the song is found on lyrics.com, query azlyrics instead
                if match == False:
                    q.put(s)
                    if not thread.is_alive():
                        thread = threading.Thread(target=az, args=())
                        thread.start()

                    dump_func("errors", errors)
                    

        songs = songs[count:]
        dump_func("unique", songs)
