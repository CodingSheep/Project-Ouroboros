# Project Ouroboros
A Locally Hosted Playlist Creator intended to be used to more easily play audio files without delay on tools such as Kenku FM.

Frankly, Kenku FM's current implementation of its Playlists and Soundboards are insufficient for more dynamic music to be played during TTRPG sessions.
As such, I'm building this tool to account for more custom audio file usage, allowing for less downtime between audio loops as well as allowing for a more seamless experience. This is to emulate adaptive/dynamic audio that you might hear in video game fights.
Yes, the website is fairly barebones, but it works for the purposes of what I'd like to use it for.

# Running the application
- Create a Python virtual environment using a tool of your choosing (venv, Anaconda, etc) using the attached environment.yml file
- Navigate to the project folder and run `flask run` or `python app.py`
- Go to https://localhost:5000 and you're ready to go.

# Using the application
- Create a playlist, then in the playlist, you can add audio files, reorder then, and choose whether you want individual ones to loop.
- If a file is not set to loop, the application will automatically play the next in sequence until the playlist is finished.
- Playlists are locally stored to a playlists.json, with audio files copied to a locally stored static/uploads folder.

# License
This project is licensed using GPL-3. Please see LICENSE for more information.