#Ubuntu 22.04 assumed. distro not yet decided by flight software team.
#TODO: Update FROM line if the payload target changes.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

#SDL_VIDEODRIVER=offscreen tells SDL2 to render without a display.
#This is cleaner than running Xvfb for pure headless operation.
#SDL_AUDIODRIVER=dummy suppresses audio init errors (Doom tries to open audio).
ENV SDL_VIDEODRIVER=offscreen
ENV SDL_AUDIODRIVER=dummy

#System dependencies required by VizDoom's pip wheel on Ubuntu 22.04.
#libsdl2-dev: SDL2 display/input backend
#libjpeg-dev, zlib1g-dev: image format support used by the engine
#libboost-all-dev, cmake: required if vizdoom builds from source as fallback
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    libsdl2-dev \
    libjpeg-dev \
    zlib1g-dev \
    libboost-all-dev \
    cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

#Install Python dependencies before copying source so this layer is cached
#as long as requirements.txt doesn't change.
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

#doom.wad is gitignored and must be mounted at runtime, it cannot be bundled
#in the image for licensing reasons. 
#Mount with: docker run -v /path/to/doom.wad:/app/maps/wads/doom.wad doomsat
#The maps/wads/ directory is created here so the mount point exists.
RUN mkdir -p maps/wads

#Default: single headless episode on E1M1.
#Override map with: docker run doomsat python3 main.py run --headless --map E1M2
CMD ["python3", "main.py", "run", "--headless"]