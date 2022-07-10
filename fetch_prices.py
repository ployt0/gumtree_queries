#!/usr/bin/env python3
import csv
import glob
import json
import time
from datetime import datetime, timedelta
from random import random, shuffle, choice
from typing import List, Dict, Any

from selenium import webdriver, common
from selenium.webdriver.common.by import By
from jinja2 import Template


def extend(row, new_style_row):
    next_date_posted = get_date_from_old_row(row)
    min_posted = datetime.strptime(new_style_row[0], "%y%m%d %H%M")
    max_posted = datetime.strptime(new_style_row[1], "%y%m%d %H%M")
    if next_date_posted < min_posted:
        new_style_row[0] = next_date_posted.strftime("%y%m%d %H%M")
    elif next_date_posted > max_posted:
        new_style_row[1] = next_date_posted.strftime("%y%m%d %H%M")
    else:
        raise RuntimeError("WTA datetime?")
    next_price = float(row[4].replace("£","").replace(",",""))
    if next_price < float(new_style_row[3]):
        new_style_row[3] = "{:6.2f}".format(next_price)
    elif next_price > float(new_style_row[2]):
        new_style_row[2] = "{:6.2f}".format(next_price)


def expand(row):
    date_posted = get_date_from_old_row(row) - timedelta(days=float(row[3]))
    return [date_posted.strftime("%y%m%d %H%M"),
            date_posted.strftime("%y%m%d %H%M"),
            "{:6.2f}".format(float(row[4].replace("£", "").replace(",", ""))),
            "{:6.2f}".format(float(row[4].replace("£", "").replace(",", ""))),
            *row[5:]]


def get_date_from_old_row(row):
    return datetime.strptime(row[0] + row[1], "%y%m%d%H%M")


def add_or_extend(index_ads, old_style_row):
    if old_style_row[2] in index_ads:
        extend(old_style_row, index_ads[old_style_row[2]])
    else:
        index_ads[old_style_row[2]] = expand(old_style_row)


def read_gumtree_spanfile(file_name) -> Dict[str, List]:
    index_ads = {}
    with open(file_name, "r", newline='') as f:
        for row in csv.reader(f):
            index_ads[row[0]] = row[1:]
    return index_ads


def scrape_gumtree(file_name, url):
    nowtime = datetime.utcnow()
    search_date_index = nowtime.strftime("%y%m%d")
    search_time = nowtime.strftime("%H%M")
    index_ads = read_gumtree_spanfile(file_name)
    pre_existing_row_cnt = len(index_ads.keys())
    driver = random_driver_opts()
    driver.get(url)
    id_pool = set()
    while True:
        time.sleep(random() * 4 + 6)
        elems = driver.find_elements(By.CLASS_NAME, "listing-link")
        last_scroll = 0
        for i, elem in enumerate(elems):
            close_modal_lightbox(driver)
            accept_privacy(driver)
            if random() > 0.8 or i - last_scroll > 5:
                driver.execute_script("arguments[0].scrollIntoView();", elem)
                last_scroll = i
                time.sleep(random() * 0.8 + 0.4)

            ad_id = elem.get_attribute("href").split("/")[-1]
            if not ad_id or ad_id in id_pool:
                continue
            title = elem.find_element(By.CLASS_NAME, "listing-title").text
            time_ago = elem.find_element(By.CLASS_NAME, "listing-posted-date").text.split("\n")[-1].split()
            if time_ago[0].upper() == "URGENT":
                continue
            elif time_ago == ["Just", "now"]:
                days_ago = 0.0
            else:
                days_ago = float(time_ago[0])
                if time_ago[1].startswith("hour"):
                    days_ago /= 24.0
            price = elem.find_element(By.CLASS_NAME, "listing-price").text
            desc = elem.find_element(By.CLASS_NAME, "listing-description").text
            add_or_extend(
                index_ads,
                [search_date_index, search_time, ad_id, "{:05.2f}".format(days_ago),
                 price, title, desc])
            id_pool.add(ad_id)
        pag_next_elems = driver.find_elements(By.CLASS_NAME, "pagination-next")
        if not pag_next_elems:
            if not driver.find_elements():
                print("No next page for {}: {}".format(
                    file_name, driver.current_url))
                # This has been observed to occur for 2 reasons:
                # 1. all the adverts fit on one page.
                # 2. we're being throttled and the page hasn't loaded.
            break
        is_disabled = pag_next_elems[0].find_elements(By.CLASS_NAME, "pagination-disabled")
        if is_disabled:
            break
        pag_next_btn = pag_next_elems[0].find_element(By.CLASS_NAME, "btn-primary")
        try:
            pag_next_btn.click()
        except common.exceptions.ElementClickInterceptedException:
            close_modal_lightbox(driver)
            pag_next_btn.click()
    driver.close()
    current_row_cnt = len(index_ads.keys())
    print("Added {} listings to the {} previously found.".format(
        current_row_cnt - pre_existing_row_cnt, pre_existing_row_cnt))
    with open(file_name, "w", newline='') as f:
        ad_writer = csv.writer(f)
        for id, data in index_ads.items():
            ad_writer.writerow([id, *data])


def random_driver_opts():
    """WIP,  --headless would be good to get in here, but we need proper error
    alerting in that case, to at least do a screen cap."""
    options = webdriver.FirefoxOptions()
    options.add_argument("--width=" + choice(["2560", "1920", "1420"]))
    options.add_argument("--height=" + choice(["1440", "1080"]))
    driver = webdriver.Firefox(options=options)
    return driver


def accept_privacy(driver):
    ot_cont = driver.find_elements(By.CLASS_NAME, "ot-sdk-container")
    if ot_cont:
        accept_btn = ot_cont[0].find_element(
            By.ID, "onetrust-accept-btn-handler")
        if accept_btn.is_displayed():
            accept_btn.click()
            time.sleep(random() * 2 + 1)


def close_modal_lightbox(driver):
    lb_cont = driver.find_elements(By.CLASS_NAME, "lightbox-content")
    if lb_cont:
        lb_closer = lb_cont[0].find_element(By.CLASS_NAME, "icon--close-alt")
        if lb_closer.is_displayed():
            lb_closer.click()
            time.sleep(random() + 0.5)


def index_ads_to_json(index_ads) -> List[Dict[str, Any]]:
    return [
        {
            "id": k,
            "from": v[0],
            "to": v[1],
            "asked": v[2],
            "asking": v[3],
            "title": v[4],
            "description": v[5],
        }
        for k, v in index_ads.items()
    ]


# Randomise/normalise access by not going after both in the same run.
# I find blank results get returned when I run all four together so tend to run
# just 2 at a time, wait an hour or so, then complete the other two.
_GT_PARAMS_LIST = [
    # ("gt_1660_gpu.csv", "https://www.gumtree.com/search?sort=date&search_category=video-cards-sound-cards&q=1660&search_location=uk"),
    # ("gt_1660_pc.csv", "https://www.gumtree.com/search?sort=date&search_category=desktop-workstation-pcs&q=1660&search_location=uk"),
    ("gt_2060_gpu.csv", "https://www.gumtree.com/search?sort=date&search_category=video-cards-sound-cards&q=2060&search_location=uk"),
    ("gt_2060_pc.csv", "https://www.gumtree.com/search?sort=date&search_category=desktop-workstation-pcs&q=2060&search_location=uk")
]


def scrape_gumtree_pcs_and_cards():
    shuffle(_GT_PARAMS_LIST)
    for i, params in enumerate(_GT_PARAMS_LIST):
        scrape_gumtree(*params)
        if i != len(_GT_PARAMS_LIST) - 1:
            time.sleep(random() * 30 + 10)


def make_webpage():
    dbl_index_ads = {}
    for gt_file in glob.glob("gt_*.csv"):
        index_ads = read_gumtree_spanfile(gt_file)
        dbl_index_ads[gt_file.split(".")[0]] = index_ads_to_json(index_ads)

    with open("results_template.html") as f_in:
        template = Template(f_in.read())
    with open("results_page.html", "w") as f_out:
        f_out.write(template.render({ "gt_results": dbl_index_ads }))


def read_json(file_name: str):
    listings = {}
    try:
        with open(file_name, "r") as f:
            listings = json.load(f)
    except FileNotFoundError:
        pass
    return listings


if __name__ == "__main__":
    scrape_gumtree_pcs_and_cards()
    make_webpage()

