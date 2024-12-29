import os
import json
import requests
import yt_dlp
import eyed3
from bs4 import BeautifulSoup

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file '{config_path}' not found. Please create it.")
    with open(config_path, "r") as f:
        return json.load(f)

def ensure_directory(directory_name):
    # Verilen dizin adını kontrol eder, eğer yoksa oluşturur ve oluşturulan dizin yolunu döndürür.
    # Checks if the given directory exists, creates it if not, and returns the directory path.
    dir_path = os.path.join(os.path.dirname(__file__), directory_name)
    os.makedirs(dir_path, exist_ok=True)
    return dir_path

def download_album_cover(cover_url, save_path):
    # Belirtilen URL'den albüm kapağını indirir ve belirtilen yola kaydeder.
    # Downloads the album cover from the specified URL and saves it to the given path.
    try:
        response = requests.get(cover_url, stream=True)
        response.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(response.content)
        print(f"Album cover saved to: {save_path}")
        return save_path
    except requests.exceptions.RequestException as e:
        print(f"Error downloading album cover: {e}")
    return None

def search_google_images(query, max_results=5):
    # Google Görseller'de belirtilen sorgu için arama yapar ve en fazla belirlenen sayıda sonuç döndürür.
    # Searches Google Images for the specified query and returns up to the maximum number of results.
    url = f"https://www.google.com/search?tbm=isch&q={query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    results = []
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            images = soup.find_all("img")
            for img in images:
                src = img.get("src")
                if src and src.startswith("http"):
                    results.append(src)
                if len(results) >= max_results:
                    break
    except Exception as e:
        print(f"Error searching Google Images: {e}")
    return results

def search_genius(song_name, artist):
    # Genius API'sini kullanarak şarkı ve sanatçı için albüm kapağı URL'lerini arar.
    # Uses the Genius API to search for album cover URLs for the given song and artist.
    query = f"{song_name} {artist}"
    url = f"https://genius.com/api/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    results = []
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            for hit in data["response"]["hits"]:
                if hit["result"]["song_art_image_url"]:
                    results.append(hit["result"]["song_art_image_url"])
    except Exception as e:
        print(f"Error searching Genius: {e}")
    return results

def fetch_album_covers(song_name, album, artist):
    # Albüm kapaklarını Google Görseller ve Genius API'den toplar ve birleştirir.
    # Combines album covers from Google Images and the Genius API into a single list.
    query = f"{song_name} {album} {artist} album cover"
    print(f"Searching for album covers: {query}")
    google_covers = search_google_images(query)
    genius_covers = search_genius(song_name, artist)
    covers = list(dict.fromkeys(google_covers + genius_covers))
    return covers[:5]

def search_youtube(song_name, artist):
    # YouTube'da şarkıyı arar ve en alakalı sonuçları döndürür.
    # Searches YouTube for the given song and artist and returns the most relevant results.
    query = f"{song_name} {artist} audio"
    print(f"Searching YouTube for: {query}")
    ydl_opts = {
        "quiet": True,
        "format": "bestaudio/best",
        "default_search": "ytsearch",
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(query, download=False)
            if "entries" in results and results["entries"]:
                return results["entries"]
    except Exception as e:
        print(f"Error searching YouTube: {e}")
    return []

def download_audio(video_url, output_file, ffmpeg_location):
    # YouTube URL'sinden ses dosyasını indirir ve MP3 formatına dönüştürür.
    # Downloads audio from the given YouTube URL and converts it to MP3 format.
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_file.rsplit(".mp3", 1)[0],
        "quiet": False,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "ffmpeg_location": ffmpeg_location,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        if not os.path.exists(output_file):
            raise FileNotFoundError(f"Audio file '{output_file}' was not created.")
        return output_file
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None

def tag_mp3_with_eyed3(file_path, song_name, artist, album, cover_path=None, genre=""):
    # MP3 dosyasını başlık, sanatçı, albüm, tür bilgileriyle etiketler ve albüm kapağını dosyaya gömer.
    # Tags the MP3 file with title, artist, album, genre, and embeds the album cover.
    try:
        audiofile = eyed3.load(file_path)
        if not audiofile.tag:
            audiofile.initTag()
        audiofile.tag.title = song_name
        audiofile.tag.artist = artist
        audiofile.tag.album = album
        audiofile.tag.genre = genre
        if cover_path and os.path.exists(cover_path):
            with open(cover_path, "rb") as img:
                audiofile.tag.images.set(eyed3.id3.frames.ImageFrame.FRONT_COVER, img.read(), "image/jpeg")
            print("Album cover successfully embedded!")
        audiofile.tag.save(version=eyed3.id3.ID3_V2_3)
    except Exception as e:
        print(f"Error tagging MP3 file with album cover: {e}")

def main():
    # Ana işlev, kullanıcıdan giriş alır, şarkıyı indirir, etiketler ve döngü içinde çalışır.
    # The main function handles user input, downloads songs, tags them, and runs in a loop.
    try:
        config = load_config()
        ffmpeg_location = config.get("ffmpeg_location")
        if not ffmpeg_location or not os.path.exists(os.path.join(ffmpeg_location, "ffmpeg.exe")):
            raise ValueError("Invalid or missing ffmpeg location in configuration. Ensure ffmpeg is correctly installed.")

        output_dir = ensure_directory("Downloads")
        album_cover_dir = ensure_directory("Album Covers")

        while True:
            song_name = input("Enter the song name: ").strip()
            artist = input("Enter the artist name: ").strip()
            album = input("Enter the album name (or press Enter to skip): ").strip() or "Unknown Album"
            genre = input("Enter the genre (or press Enter to skip): ").strip() or "Unknown Genre"

            if not song_name or not artist:
                print("Song name and artist cannot be empty. Please try again.")
                continue

            covers = fetch_album_covers(song_name, album, artist)
            cover_path = None
            if covers:
                print("\nChoose an album cover:")
                for i, cover in enumerate(covers, 1):
                    print(f"{i}. {cover}")
                print("0. Skip album cover")
                try:
                    choice = int(input("Enter the number of the cover to use (or 0 to skip): ").strip())
                    if choice > 0:
                        selected_cover = covers[choice - 1]
                        save_path = os.path.join(album_cover_dir, f"{song_name}_{artist}.jpg")
                        cover_path = download_album_cover(selected_cover, save_path)
                except (ValueError, IndexError):
                    print("Invalid choice. Skipping album cover.")

            videos = search_youtube(song_name, artist)
            if not videos:
                print(f"Could not find any matches for '{song_name}' by '{artist}'. Please refine your search.")
                continue

            print("\nFound the following results:")
            for i, video in enumerate(videos[:5], 1):
                print(f"{i}. {video['title']} ({video['webpage_url']})")

            try:
                choice = int(input("Enter the number of the correct video (or 0 to exit): ").strip())
                if choice == 0:
                    print("Exiting.")
                    return
                selected_video = videos[choice - 1]
            except (ValueError, IndexError):
                print("Invalid selection. Please try again.")
                continue

            output_file = os.path.join(output_dir, f"{song_name} - {artist}.mp3")
            print("\nDownloading audio...")
            final_file = download_audio(selected_video["webpage_url"], output_file, ffmpeg_location)
            if final_file:
                print("Tagging MP3 file...")
                tag_mp3_with_eyed3(final_file, song_name, artist, album, cover_path, genre)
                print(f"\nDone! The file is saved as: {final_file}")
            else:
                print("Failed to download the audio. Skipping tagging.")

            continue_choice = input("\nDo you want to download another song? (yes/no): ").strip().lower()
            if continue_choice != "yes":
                print("Exiting. Goodbye!")
                break

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
