# cCAS Systems Dev Engineer Take-Home Assessment

---

## Introduction

For this assessment, we’ll be focusing on your ability to create a service that consumes an API endpoint, manipulate the data retrieved, publish the data to another API, and package a solution in a Docker container. 

Here are some things to think about before you dive in:

* **Documentation**: Provide documentation that explains your system, your decision-making process, and anything else that you feel is important.

* **Quality:** Build your service as if they were going to be adopted by our team and put into production. Include some tests or a way to validate that your service works properly as well as logging.

* **Tech Stack:** While we are most comfortable reading Java, Go, and Python, you should use whatever languages and tools **you** are most comfortable with. 

* **Timeline:** You will have 24 hours to complete the project and submit your code. Please submit your code at least 4 hours before your review.

## Requirements

* **API Consumption**: In the [Setup](#setup) section below, you will be provided with documentation for a public API endpoint that contains weather data ([wttr](https://wttr.in/)). Your task is to build a script or application that retrieves this data from the API every 30 seconds and publishes that information to influxDB as a time-series. You will pull records from 10 cities of your choosing across no less than 2 countries.  
* **Data Manipulation**: Once you’ve retrieved the data, you may need to manipulate it in some way. We want to record the following data in infuxDB.  
  * Humidity  
  * Pressure  
  * Temperature (celcius)  
  * Temperature (fahrenheit)  
  * Temperature (kelvin)  
  * Country  
  * Cloudcover  
  * Latitude  
  * Longitude  
* **Authentication**: Ensure that your application includes the necessary logic to authenticate requests to the InfluxDB instance. Note: The wttr API mentioned does not require authentication.   
* **Docker Container**: Your final delivery will be a Docker container that can be deployed and has the functionality for API consumption, along with your source code. Add your solution as a new service to the existing docker-compose configuration provided below. This would allow us to bring up your service along with the InfluxDB service using a single docker compose up command. Please ensure necessary scripts for building and running your service are included in your submission.  
* **Review**: Be prepared to walk through your implementation and potentially extend it.  
* **Submission**: Please submit your response [here](https://drive.google.com/drive/folders/1obvHZO6kkNPQL-rHl5MjDu0CwLd0iFw_).

### Bonus Points

* Think about how this may need to scale and build in features that could aid in that scalability. *Hint*, *think of concurrency.*

## Setup {#setup}

### Influxdb

To help you start your local [influxDB](https://docs.influxdata.com/influxdb/cloud/reference/api/) container, we have provided a sample docker-compose.yml file below. You are encouraged to use this configuration and add your implementation as an additional service in this docker-compose config.

```
# docker config for influx db
services:
  influxdb2:
    image: influxdb:2
    container_name: influxdb2
    ports:
      - "8086:8086"
    volumes:
      - type: bind
        source: ./influxdb2_data
        target: /var/lib/influxdb2
      - type: bind
        source: ./influxdb2_config
        target: /etc/influxdb2
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=admin
      - DOCKER_INFLUXDB_INIT_PASSWORD=admin123!
      - DOCKER_INFLUXDB_INIT_ORG=nflx
      - DOCKER_INFLUXDB_INIT_BUCKET=default
```

*Once the influx service has launched, `influxdb2_config/influx-configs` will contain the token for the admin user. You can use this token to read and write to influxDB.* 

### WTTR

[Wttr](https://wttr.in/) will be your source of weather information. Git repo is located [here](https://github.com/chubin/wttr.in). 

## Closing Thoughts

We want to see if you can build a simple but non-trivial system. We appreciate you taking the time to do this, and we’ll show our appreciation by giving you as much feedback on the submission as you'd like.

Lastly, **have fun.**

We realize that interview-related coding exercises are stressful, so we’ve tried to make this as enjoyable as possible. Please do not hesitate to let us know how you felt about it before, during, and after this part of the process.

