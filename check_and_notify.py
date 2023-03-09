import os

import re
import time
from typing import List

import requests
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait

new_table_body_xpath = "(//*[contains(concat('', @class), ' onboardingWindow_spot-container')]//*[contains(concat(''," \
                       " @class), 'MuiTableBody-root')])[1] "
max_seconds_for_wait = 30


def login():
    jet_login = os.environ['JET_LOGIN']
    jet_password = os.environ['JET_PASSWORD']
    driver.get("https://jetlend.ru/invest/login/")
    waitDriver.until(ec.visibility_of_element_located((By.XPATH, "//*[text()[contains(.,'Войти')]]")))
    driver.find_element(By.ID, "_phone").send_keys(jet_login)
    driver.find_element(By.ID, "_password").send_keys(jet_password)
    driver.find_element(By.XPATH, "//div[@class='submit-container']/button[@type='submit']").click()
    free_amount_xpath = "//*[text()[contains(.,'Свободно')]]/../../../div[contains(concat('', @class), " \
                        "'legendItem_right')] "
    waitDriver.until(ec.visibility_of_element_located((By.XPATH, free_amount_xpath)))

    amount_str = "0.0"
    for i in range(max_seconds_for_wait):
        amount_web = driver.find_element(By.XPATH, free_amount_xpath).text
        amount_str = re.sub('([\\d,]+) .*', '\\1', amount_web).translate(str.maketrans(",", "."))
        if amount_str != '- (-)':
            break
        time.sleep(1)

    return float(amount_str)


def open_market():
    driver.get("https://jetlend.ru/invest/v3/market")
    waitDriver.until(ec.visibility_of_element_located((By.XPATH, new_table_body_xpath)))


def get_columns() -> List[str]:
    new_table_head_xpath = "(//*[contains(concat('', @class), ' onboardingWindow_spot-container')]//*[contains(" \
                           "concat('', @class), 'MuiTableHead-root')])[2] "
    header = driver.find_element(By.XPATH, new_table_head_xpath)
    return header.text.split("\n")


def get_rows() -> List[List[str]]:
    rows_number_select_xpath = "(//div[contains(@class, 'MuiInputBase-root MuiTablePagination-input " \
                               "MuiTablePagination-selectRoot')])[1] "
    waitDriver.until(ec.visibility_of_element_located((By.XPATH, rows_number_select_xpath)))
    selector = driver.find_element(By.XPATH, rows_number_select_xpath)
    driver.execute_script("window.scrollTo(0, " + str(selector.location['y'] - 100) + ")")
    ActionChains(driver).move_to_element(selector).click(selector).perform()

    elem100_xpath = "//li[contains(@data-value, '100')]"
    waitDriver.until(ec.visibility_of_element_located((By.XPATH, elem100_xpath)))
    driver.find_element(By.XPATH, elem100_xpath).click()

    elements = driver.find_elements(By.XPATH,
                                    f"{new_table_body_xpath}//*[contains(concat('', @class), 'MuiTableRow-root')]")
    return list(map(lambda element: element.text.split("\n"), elements))


def get_exclude_invested(rows: List[List[str]], columns: List[str]) -> List[List[str]]:
    idx = columns.index("В портфеле") + 1
    return list(filter(lambda row: row[idx] == "-", rows))


def get_exclude_type_c(rows: List[List[str]], columns: List[str]) -> List[List[str]]:
    idx = columns.index("Рейтинг") + 1
    return list(filter(lambda row: row[idx] != "C", rows))


def get_exclude_smalls_percent(source: List[List[str]], columns: List[str]) -> List[List[str]]:
    minimal_interest_income = 16.0

    idx = columns.index("Ставка") + 1
    for i in range(len(source)):
        line = source[i]
        line[idx] = re.sub(r"(\d+)(,?)(\d*)%.*", "\\1\\2\\3", line[idx]).replace(",", ".")

    result = list(filter(lambda row: float(row[idx]) >= minimal_interest_income, source))
    result.sort(key=lambda item: -float(item[idx]))

    return result


def get_exclude_reserved(rows: List[List[str]], columns: List[str]) -> List[List[str]]:
    idx = columns.index("Резерв") + 1
    return list(filter(lambda row: row[idx] == "-", rows))


def get_exclude_already_collected(rows: List[List[str]], columns: List[str]) -> List[List[str]]:
    idx = columns.index("График сбора") + 1
    for i in range(len(rows)):
        line = rows[i]
        # noinspection PyTypeChecker
        line[idx] = re.sub(r".*\s(\d+)\s.*", "\\1", line[idx])

    result = list(filter(lambda row: int(row[idx]) < 100, rows))
    return result


def filter_and_sort(rows: List[List[str]], columns: List[str]) -> List[List[str]]:
    exclude_smalls_percent = get_exclude_smalls_percent(rows, columns)
    exclude_type_c = get_exclude_type_c(exclude_smalls_percent, columns)
    exclude_invested = get_exclude_invested(exclude_type_c, columns)
    exclude_reserved = get_exclude_reserved(exclude_invested, columns)
    exclude_already_collected = get_exclude_already_collected(exclude_reserved, columns)
    return exclude_already_collected


options = Options()
options.headless = True
options.set_capability("useAutomationExtension", "false")
options.add_argument("disable-infobars")
options.add_argument("disable-extensions")
options.add_argument("--no-sandbox")
options.add_argument("--headless")
options.add_argument("--shm-size=\"2g\"")
options.add_argument("--disable-gpu")

with webdriver.Chrome(options=options, service=(Service(os.environ['CHROMEDRIVER_PATH']))) as driver:
    waitDriver = WebDriverWait(driver, max_seconds_for_wait)
    amount = login()
    open_market()
    all_rows = get_rows()
    all_columns = get_columns()
    result_to_invest = filter_and_sort(all_rows, all_columns)
    nl = "\n"
    table = nl.join(map(lambda row: f"{row[0][0:8]} {row[3]}% // {row[4]} {row[6]}%", result_to_invest))
    output = f"Свободно: {amount} руб{nl}{nl}{table}"
    telegram_bot_id = os.environ['TELEGRAM_BOT_ID']
    telegram_chat_id = os.environ['TELEGRAM_CHAT_ID']
    requests.get(f'https://api.telegram.org/bot{telegram_bot_id}/sendMessage?chat_id={telegram_chat_id}&text={output}')

    print(output)
