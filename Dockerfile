FROM python:3.12-slim
USER root

RUN apt-get update -y \
	&& apt-get upgrade -y \
	&& apt-get autoremove -y
RUN apt-get install git -y
RUN apt-get install sudo -y \
	&& apt-get install systemctl -y
RUN apt-get -y install locales && \
	localedef -f UTF-8 -i ja_JP ja_JP.UTF-8
ENV LANG ja_JP.UTF-8
ENV LANGUAGE ja_JP:ja
ENV LC_ALL ja_JP.UTF-8
ENV TZ JST-9

RUN pip install --upgrade pip
RUN pip install --upgrade setuptools
COPY app/requirements.txt /root/opt/app/requirements.txt
RUN pip install -r /root/opt/app/requirements.txt

CMD ["python", "/root/opt/app/src/main.py"]