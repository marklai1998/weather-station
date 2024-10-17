#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
# import json
from os import walk
import operator

libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
assetsdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'assets')

if os.path.exists(libdir):
    sys.path.append(libdir)

import logging
from waveshare_epd import epd7in5_V2
from PIL import Image, ImageDraw, ImageFont
import atexit
import time
from datetime import datetime
import threading
import requests

# with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'res.json')) as file:
#     data = json.load(file)

# Setup
logging.basicConfig(level=logging.DEBUG)

font20 = ImageFont.truetype(os.path.join(assetsdir, 'NimbusSanL-Reg.otf'), 20)
font24 = ImageFont.truetype(os.path.join(assetsdir, 'NimbusSanL-Reg.otf'), 24)
font32 = ImageFont.truetype(os.path.join(assetsdir, 'NimbusSanL-Reg.otf'), 32)
font18 = ImageFont.truetype(os.path.join(assetsdir, 'NimbusSanL-Reg.otf'), 18)
font12 = ImageFont.truetype(os.path.join(assetsdir, 'NimbusSanL-Reg.otf'), 12)
font64 = ImageFont.truetype(os.path.join(assetsdir, 'NimbusSanL-Reg.otf'), 64)
font16 = ImageFont.truetype(os.path.join(assetsdir, 'NimbusSanL-Reg.otf'), 16)
font10 = ImageFont.truetype(os.path.join(assetsdir, 'NimbusSanL-Reg.otf'), 10)
font14 = ImageFont.truetype(os.path.join(assetsdir, 'NimbusSanL-Reg.otf'), 14)

downImg = Image.open(os.path.join(assetsdir, "down.png"))
upImg = Image.open(os.path.join(assetsdir, "up.png"))
windImg = Image.open(os.path.join(assetsdir, "wind.png"))
humidityImg = Image.open(os.path.join(assetsdir, "humidity.png"))
rainLevelImg = Image.open(os.path.join(assetsdir, "rainLevel.png"))
snowLevelImg = Image.open(os.path.join(assetsdir, "snowLevel.png"))

weatherImages = {}
for (dirpath, dirnames, filenames) in walk(os.path.join(assetsdir, f"weathers")):
    for filename in filenames:
        weatherImages[filename.split('.')[0]] = Image.open(os.path.join(assetsdir, f"weathers/{filename}")).convert(
            "RGBA")
    break

guideLine = False
shuttingDown = False
epd = epd7in5_V2.EPD()
epd.init()
epd.Clear()
epd.init_part()

apiKey = os.environ['API_KEY']
data = None


def text(d, cord, st, **args):
    d.text(cord, st, **args)
    return d.textbbox(cord, st, **args)


def getCanvas(size):
    width, height = size
    image = Image.new('1', (width, height), 255)
    draw = ImageDraw.Draw(image)
    if guideLine: draw.rectangle((0, 0, width - 1, height - 1))
    return image, draw


class CurrentWeatherWidget:
    width = 200
    height = 160

    currentWeatherLastRefresh = int(time.time())
    currentWeatherIdx = 0

    def getWidget(self, data):
        image, draw = getCanvas((self.width, self.height))

        currentWeathers = data.get('current').get('weather')
        weatherLength = len(currentWeathers)

        if int(time.time()) - self.currentWeatherLastRefresh >= 5:
            if self.currentWeatherIdx + 1 >= weatherLength:
                self.currentWeatherIdx = 0
            else:
                self.currentWeatherIdx = self.currentWeatherIdx + 1
            self.currentWeatherLastRefresh = int(time.time())

        weather = currentWeathers[self.currentWeatherIdx]

        imgCode = weather.get('icon') or None
        file = imgCode[0:2] if imgCode is not None else None

        try:
            weatherImage = weatherImages[file] if file is not None else None
            draw.bitmap((36, 8), weatherImage)
        except  BaseException as e:
            logging.info(e)
            draw.rectangle((36, 8, 36 + 128, 8 + 128))

        descriptionBbox = draw.textbbox((100, 138), weather.get('description').title() or '', font=font16,
                                        anchor='mt', align='center')
        descriptionFont = font12 if descriptionBbox[2] - descriptionBbox[0] >= 200 else font16
        text(draw, (100, 138), weather.get('description').title() or '', font=descriptionFont,
             anchor='mt', align='center')

        if weatherLength > 1:
            weathersCounter = text(draw, (164, 136), f"{self.currentWeatherIdx + 1}/{weatherLength}", font=font20,
                                   anchor='rd')
            draw.rectangle(
                (weathersCounter[0] - 2, weathersCounter[1] - 2, weathersCounter[2] + 2, weathersCounter[3] + 2),
                fill=255, outline=0)
            text(draw, (164, 136), f"{self.currentWeatherIdx + 1}/{weatherLength}", font=font20,
                 anchor='rd')

        return image


class ClockWidget:
    width = 200
    height = 56

    def getWidget(self, data):
        image, draw = getCanvas((self.width, self.height))

        textStyle = {
            "font": font20,
            "anchor": "ms",
            "align": "center",
        }
        heightMid = self.height / 2
        text(draw, (self.width / 2, heightMid), time.strftime('%Y-%m-%d').upper(), **textStyle)
        text(draw, (self.width / 2, heightMid + 20), time.strftime('%a %I:%M:%S%p').upper(), **textStyle)

        return image


class CurrentTempWidget:
    width = 200
    height = 96

    def getWidget(self, data):
        image, draw = getCanvas((self.width, self.height))

        current = data.get('current')
        today = data.get('daily')[0]

        text(draw, (20, 64), f"{round(current.get('temp') or 0)}°", font=font64, anchor='ls')
        text(draw, (137, 44), f"Feels like", font=font12, anchor='ls')
        text(draw, (137, 64), f"{round(current.get('feels_like') or 0)}°", font=font20, anchor='ls')

        draw.bitmap((20, 72), upImg)
        text(draw, (38, 88), f"{round(today.get('temp').get('max'))}°", font=font20, anchor='ls')
        draw.bitmap((80, 72), downImg)
        text(draw, (98, 88), f"{round(today.get('temp').get('min'))}°", font=font20, anchor='ls')

        return image


class StatsWidget:
    width = 200
    height = 168

    def getWidget(self, data):
        image, draw = getCanvas((self.width, self.height))

        current = data.get('current')

        draw.bitmap((40, 24), windImg)
        wind = text(draw, (72, 48), f"{round(current.get('wind_speed') or 0)}", font=font24, anchor='ls')
        text(draw, (wind[2] + 1, wind[3]), "mph", font=font12, anchor='ls')

        draw.bitmap((40, 56), humidityImg)
        humidity = text(draw, (72, 80), f"{round(current.get('humidity') or 0)}", font=font24, anchor='ls')
        text(draw, (humidity[2] + 1, humidity[3]), "%", font=font12, anchor='ls')

        draw.bitmap((40, 88), rainLevelImg)
        rain = text(draw, (72, 112), f"{round(current.get('rain') or 0)}", font=font24, anchor='ls')
        text(draw, (rain[2] + 1, rain[3]), "mm", font=font12, anchor='ls')

        draw.bitmap((40, 120), snowLevelImg)
        snow = text(draw, (72, 144), f"{round(current.get('snow') or 0)}", font=font24, anchor='ls')
        text(draw, (snow[2] + 1, snow[3]), "mm", font=font12, anchor='ls')

        return image


class DayEstWidget:
    width = 600
    height = 136

    def getItem(self, data):
        image, draw = getCanvas((80, 136))

        weather = data.get('weather')[0]

        imgCode = weather.get('icon') or None
        file = imgCode[0:2] if imgCode is not None else None

        try:
            weatherImage = weatherImages[file] if file is not None else None
            draw.bitmap((16, 32), weatherImage.resize((48, 48)))
        except  BaseException as e:
            logging.info(e)
            draw.rectangle((16, 32, 16 + 48, 32 + 48))

        text(draw, (80 / 2, 28), datetime.fromtimestamp(data.get('dt')).strftime('%I%p').upper(), font=font20,
             anchor='ms', align='center')
        text(draw, (80 / 2, 104), f"{round(data.get('temp'))}°", font=font32, anchor='ms', align='center')

        if data.get('pop') > 0:
            rainRop = text(draw, (80 / 2 + 12, 124), f"{round(data.get('pop') * 100)}%", font=font20, anchor='ms',
                           align='center')
            draw.bitmap((rainRop[0] - 24, rainRop[1] - 2), rainLevelImg.resize((24, 24)))

        return image

    def getWidget(self, data):
        image, draw = getCanvas((self.width, self.height))

        thisHour, *otherHours = data.get('hourly') or []

        for idx, hour in enumerate(otherHours):
            image.paste(self.getItem(hour), (10 + (idx * (80 + 5)), 0))

        return image


class WeekEstWidget:
    width = 600
    height = 344

    def getItem(self, data):
        image, draw = getCanvas((600, 48))

        text(draw, (16, 48 / 2), datetime.fromtimestamp(data.get('dt')).strftime('%a').upper(), font=font20,
             anchor='lm', align='center')

        weather = data.get('weather')[0]

        imgCode = weather.get('icon') or None
        file = imgCode[0:2] if imgCode is not None else None

        try:
            weatherImage = weatherImages[file] if file is not None else None
            draw.bitmap((72, 4), weatherImage.resize((40, 40)))
        except BaseException as e:
            logging.info(e)
            draw.rectangle((72, 4, 72 + 40, 4 + 40))

        text(draw, (120, 48 / 2), f"{round(data.get('temp').get('day') or 0)}°", font=font32, anchor='lm',
             align='center')

        draw.bitmap((184, 12), upImg.resize((24, 24)))
        text(draw, (208, 32), f"{round(data.get('temp').get('max') or 0)}°", font=font20, anchor='ls')
        draw.bitmap((248, 12), downImg.resize((24, 24)))
        text(draw, (272, 32), f"{round(data.get('temp').get('min') or 0)}°", font=font20, anchor='ls')

        if data.get('pop') > 0:
            draw.bitmap((312, 12), rainLevelImg.resize((24, 24)))
            text(draw, (336, 32), f"{round(data.get('pop') * 100)}%", font=font20, anchor='ls')

        return image

    def getWidget(self, data):
        image, draw = getCanvas((self.width, self.height))

        today, *otherDays = data.get('daily') or []

        for idx, day in enumerate(otherDays):
            image.paste(self.getItem(day), (0, 4 + (idx * 48)))

        return image


class PrecipitationWidget:
    width = 600
    height = 152

    def getItem(self, data):
        image, draw = getCanvas((9, 84))

        value = data.get('precipitation') or 0

        draw.rectangle((0, 84 - (4 * value), 8, 84), fill=0)

        return image

    def getWidget(self, data):
        image, draw = getCanvas((self.width, self.height))

        now = time.time()

        items = [x for x in (data.get('minutely') or []) if (x.get('dt') or 0) >= now]

        maxIndex, value = max(enumerate(map(lambda x: x.get('precipitation') or 0, items)), key=operator.itemgetter(1))

        isStopped = lambda x: x.get('precipitation') or 0 == 0
        stopItem = next((x for x in items if isStopped(x)), None)

        isStarted = lambda x: x.get('precipitation') or 0 > 0
        startItem = next((x for x in items if isStarted(x)), None)

        if items[0].get('precipitation') or 0 > 0:
            mins = round((stopItem.get('dt') - now) / 60)

            text(draw, (16, 8), f"Rain stopping in {max(0, mins)}min", font=font20, anchor='lt', align='center')
        else:
            mins = round((startItem.get('dt') - now) / 60)

            text(draw, (16, 8), f"Rain starting in {max(0, mins)}min", font=font20, anchor='lt', align='center')

        for idx, minute in enumerate(items):
            left = 30 + (idx * 9)
            image.paste(self.getItem(minute), (left, 40))

            if idx == maxIndex:
                text(draw, (left + 4, 38), f"{round(minute.get('precipitation') or 0)}mm", font=font12, anchor='ms',
                     align='center')
                draw.line([(left + 4, 40), (left + 4, 122)], fill=0, width=1)

            if idx % 10 == 0:
                text(draw, (left + 4, 140), f"{idx}min", font=font16, anchor='ms', align='center')
                draw.line([(left + 4, 124), (left + 4, 128)], fill=0, width=1)

        return image


currentWeatherWidget = CurrentWeatherWidget()
clockWidget = ClockWidget()
currentTempWidget = CurrentTempWidget()
statsWidget = StatsWidget()
weekEstWidget = WeekEstWidget()
dayEstWidget = DayEstWidget()
precipitationWidget = PrecipitationWidget()


def render():
    global shuttingDown
    while not shuttingDown:
        if not data: continue
        image, draw = getCanvas((epd.width, epd.height))

        now = time.time()
        precipitationItems = [x for x in (data.get('minutely') or []) if (x.get('dt') or 0) >= now]
        precipitation = any(item.get('precipitation') or 0 > 0 for item in precipitationItems)

        image.paste(clockWidget.getWidget(data), (0, 0))
        image.paste(currentWeatherWidget.getWidget(data), (0, 56))
        image.paste(currentTempWidget.getWidget(data), (0, 216))
        image.paste(statsWidget.getWidget(data), (0, 312))
        image.paste(dayEstWidget.getWidget(data), (200, 0))

        if precipitation:
            image.paste(precipitationWidget.getWidget(data), (200, 136))
            image.paste(weekEstWidget.getWidget(data), (200, 288))
            draw.line([(216, 288), (784, 288)], fill=0, width=1)
            # draw.line([(592, 288), (592, 464)], fill=0, width=1)
        else:
            image.paste(weekEstWidget.getWidget(data), (200, 136))
            # draw.line([(592, 152), (592, 464)], fill=0, width=1)

        # Layout
        draw.line([(200, 0), (200, 480)], fill=0, width=3)
        draw.line([(216, 136), (784, 136)], fill=0, width=1)

        try:
            epd.display_Partial(epd.getbuffer(image), 0, 0, epd.width, epd.height)
        except IOError as e:
            logging.info(e)


def openWeather():
    global data
    while not shuttingDown:
        try:
            querystring = {"lat": "43.829010", "lon": "-79.296370", "appid": apiKey,
                           "units": "metric"}

            payload = ""
            headers = {"User-Agent": "insomnia/10.0.0"}

            response = requests.request("GET", "https://api.openweathermap.org/data/3.0/onecall", data=payload,
                                        headers=headers, params=querystring)

            data = response.json()
            time.sleep(5 * 60)
        except Exception as e:
            logging.info(e)


openWeather = threading.Thread(name='render', target=openWeather)
renderer = threading.Thread(name='render', target=render)


# Shutdown hook
def shutdown():
    global shuttingDown
    logging.info("Shutdown")
    shuttingDown = True
    renderer.join()
    openWeather.join()
    epd.init()
    epd.Clear()
    epd7in5_V2.epdconfig.module_exit(cleanup=True)


atexit.register(shutdown)
renderer.start()
openWeather.start()
