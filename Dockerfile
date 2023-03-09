FROM seleniarm/standalone-chromium:latest

RUN update-rc.d -f supervisord remove

RUN \
    sudo apt -y update \
    && sudo apt install -y pip \
    && sudo apt clean \
    && true

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt
#RUN sudo apt -y purge `dpkg -l | grep -i compiler | egrep -vi '(collection|library)' | awk '{ print $2}'`
#RUN sudo apt -y purge `dpkg -l | awk '{print $2}' | grep -i -- -dev`
COPY . .
CMD python3.9 check_and_notify.py
