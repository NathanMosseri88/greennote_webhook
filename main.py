import requests
from requests.auth import HTTPBasicAuth
import requests_pkcs12
from flask import Flask, request, jsonify
from flask_cors import CORS
from waitress import serve
import logging
from xml.etree import ElementTree as ET
import xml.sax.saxutils as xml_utils
import os

app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": ["https://greennotecapitalpartners.quickbase.com"]}},
#      supports_credentials=True,
#      allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
#      methods=["GET", "POST", "OPTIONS"])
CORS(app, resources={r"/*": {"origins": ["https://greennotecapitalpartners.quickbase.com"]}})

def escape_xml(value):
    return xml_utils.escape(value) if value else ""


@app.before_request
def restrict_access():
    allowed_domains = ['https://greennotecapitalpartners.quickbase.com']
    origin = request.headers.get('Origin')
    if origin not in allowed_domains:
        return jsonify({'error': 'Unauthorized'})
#
#
# @app.after_request
# def after_request(response):
#     response.headers["Access-Control-Allow-Origin"] = "https://greennotecapitalpartners.quickbase.com, https://one-imp-mistakenly.ngrok-free.app"
#     response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
#     response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
#     response.headers["Access-Control-Allow-Credentials"] = "true"
#     return response


@app.route('/clear-person-search', methods=["POST"])
def person_search_clear():
    params = request.get_json()

    last_name = params.get('lastName')
    social = params.get('social')

    username = os.getenv("CLEAR_USERNAME")
    password = os.getenv("CLEAR_PASSWORD")
    cert_pass = os.getenv("CLEAR_CERT_PASS")
    cert_path = os.getenv("CLEAR_CERT_PATH")

    url = 'https://s2s.thomsonreuters.com/api/v3/person/searchResults'

    xml_body = f"""
        <ps:PersonSearchRequestV3 xmlns:ps="http://clear.thomsonreuters.com/api/search/2.0">
          <PermissiblePurpose>
            <GLB>B</GLB>
            <DPPA>3</DPPA>
            <VOTER>7</VOTER>
          </PermissiblePurpose>
          <Reference>S2S Person Search</Reference>
          <Criteria>
            <p1:PersonCriteria xmlns:p1="com/thomsonreuters/schemas/search">
              <NameInfo>
                <AdvancedNameSearch>
                  <LastSecondaryNameSoundSimilarOption>false</LastSecondaryNameSoundSimilarOption>
                  <SecondaryLastNameOption>OR</SecondaryLastNameOption>
                  <FirstNameBeginsWithOption>false</FirstNameBeginsWithOption>
                  <FirstNameSoundSimilarOption>false</FirstNameSoundSimilarOption>
                  <FirstNameExactMatchOption>false</FirstNameExactMatchOption>
                </AdvancedNameSearch>
                <LastName>{last_name}</LastName>
                <FirstName></FirstName>
                <MiddleInitial></MiddleInitial>
                <SecondaryLastName></SecondaryLastName>
              </NameInfo>
              <AddressInfo>
                <StreetNamesSoundSimilarOption>false</StreetNamesSoundSimilarOption>
                <Street></Street>
                <City></City>
                <State></State>
                <County></County>
                <ZipCode></ZipCode>
                <Province></Province>
                <Country></Country>
              </AddressInfo>
              <EmailAddress></EmailAddress>
              <NPINumber></NPINumber>
              <SSN>{social}</SSN>
              <PhoneNumber></PhoneNumber>
              <AgeInfo>
                <PersonBirthDate></PersonBirthDate>
                <PersonAgeTo></PersonAgeTo>
                <PersonAgeFrom></PersonAgeFrom>
              </AgeInfo>
              <DriverLicenseNumber></DriverLicenseNumber>
              <WorldCheckUniqueId></WorldCheckUniqueId>
            </p1:PersonCriteria>
          </Criteria>
          <Datasources>
            <PublicRecordPeople>true</PublicRecordPeople>
            <NPIRecord>false</NPIRecord>
            <WorldCheckRiskIntelligence>false</WorldCheckRiskIntelligence>
          </Datasources>
        </ps:PersonSearchRequestV3>
    """

    headers = {
        "Content-Type": "application/xml",
        "Accept": "application/xml"
    }

    try:
        # Send POST request
        clear_post = requests_pkcs12.post(
            url,
            data=xml_body,
            headers=headers,
            auth=HTTPBasicAuth(username, password),
            pkcs12_filename=cert_path,
            pkcs12_password=cert_pass
        )

        if clear_post.status_code != 200:
            root = ET.fromstring(clear_post.text)
            error_message = root.find('.//Message').text if root.find('.//Message') is not None else "Unknown Error"
            return jsonify({'error': error_message}), clear_post.status_code

        # Parse the response to extract the URI
        root = ET.fromstring(clear_post.text)
        group_count_element = root.find('.//GroupCount')
        group_count = int(group_count_element.text) if group_count_element is not None else 0
        if group_count == 0:
            logging.info("No results found")
            return jsonify({"message": "No results found."}), 204

        uri = root.find('.//Uri').text

        # Fetch the results using the extracted URI
        get_results = requests_pkcs12.get(
            uri,
            headers={'Accept': 'application/xml'},
            auth=HTTPBasicAuth(username, password),
            pkcs12_filename=cert_path,
            pkcs12_password=cert_pass
        )
        print(get_results.text)
        if get_results.status_code != 200:
            return jsonify({'error': "Failed to fetch person search results"}), get_results.status_code

        # Parse the results XML to extract phone numbers and relevance scores
        results_root = ET.fromstring(get_results.text)
        namespaces = {
            'ns2': 'com/thomsonreuters/schemas/common-data',
            'ns3': 'com/thomsonreuters/schemas/search',
            'ns4': 'http://clear.thomsonreuters.com/api/search/2.0',
            'ns5': 'com/thomsonreuters/schemas/globalbeneficialownership-search'
        }

        result_groups = results_root.findall('.//ns4:ResultGroup', namespaces)
        results = []

        for group in result_groups:
            group_id = group.find('./ns4:GroupId', namespaces).text if group.find('./ns4:GroupId', namespaces) else ''
            relevance = group.find('./ns4:Relevance', namespaces).text if group.find('./ns4:Relevance',
                                                                                     namespaces) else ''
            dominant_values = group.find('./ns4:DominantValues/ns3:PersonDominantValues', namespaces)

            # Initialize fields
            phone_number = firstname = lastname = middlename = fullname = ''
            social_num = birthday = age = ''
            street = city = state = zip_code = country = address_reported_date = ''

            if dominant_values is not None:
                phone_number_elem = dominant_values.find('./ns3:PhoneNumber', namespaces)
                phone_number = phone_number_elem.text if phone_number_elem else ''

                name_root = dominant_values.find('./ns3:Name', namespaces)
                if name_root:
                    firstname = name_root.find('./ns3:FirstName', namespaces)
                    lastname = name_root.find('./ns3:LastName', namespaces)
                    middlename = name_root.find('./ns3:MiddleName', namespaces)
                    fullname = name_root.find('./ns3:FullName', namespaces)

                firstname = firstname.text if firstname else ''
                lastname = lastname.text if lastname else ''
                middlename = middlename.text if middlename else ''
                fullname = fullname.text if fullname else ''

                social_num_elem = dominant_values.find('./ns3:SSN', namespaces)
                social_num = social_num_elem.text if social_num_elem else ''

                age_root = dominant_values.find('./ns3:AgeInfo', namespaces)
                if age_root:
                    birthday_elem = age_root.find('./ns3:PersonBirthDate', namespaces)
                    birthday = birthday_elem.text if birthday_elem else ''
                    age_elem = age_root.find('./ns3:PersonAge', namespaces)
                    age = age_elem.text if age_elem else ''

                address_root = dominant_values.find('./ns3:Address', namespaces)
                if address_root:
                    street_elem = address_root.find('./ns3:Street', namespaces)
                    city_elem = address_root.find('./ns3:City', namespaces)
                    state_elem = address_root.find('./ns3:State', namespaces)
                    zip_elem = address_root.find('./ns3:ZipCode', namespaces)
                    country_elem = address_root.find('./ns3:Country', namespaces)
                    reported_date_elem = address_root.find('./ns3:ReportedDate', namespaces)

                    street = street_elem.text if street_elem else ''
                    city = city_elem.text if city_elem else ''
                    state = state_elem.text if state_elem else ''
                    zip_code = zip_elem.text if zip_elem else ''
                    country = country_elem.text if country_elem else ''
                    address_reported_date = reported_date_elem.text if reported_date_elem else ''

            results.append({
                "relevance": relevance,
                "group_id": group_id,
                "search_id": uri.split('/')[-1],
                "phone_number": phone_number,
                "first_name": firstname,
                "last_name": lastname,
                "middle_name": middlename,
                "full_name": fullname,
                "social": social_num,
                "birthday": birthday,
                "age": age,
                "street": street,
                "city": city,
                "state": state,
                "zip": zip_code,
                "country": country,
                "address_reported_date": address_reported_date
            })

        sorted_results = sorted(results, key=lambda x: x['relevance'], reverse=True)
        return jsonify(sorted_results), 200

    except Exception as e:
        logging.error(f"Post Request failed: {e}")
        return jsonify({'error': 'An Internal server error occurred'}), 500


@app.route('/clear-search', methods=["POST"])
def search_clear():
    params = request.get_json()

    first_name = params.get('firstName')
    last_name = params.get('lastName')
    business_name = params.get('businessName')

    username = os.getenv("CLEAR_USERNAME")
    password = os.getenv("CLEAR_PASSWORD")
    cert_pass = os.getenv("CLEAR_CERT_PASS")
    cert_path = os.getenv("CLEAR_CERT_PATH")

    url = 'https://s2s.thomsonreuters.com/api/v2/phone/searchResults'

    xml_body = f"""
    <phs:PhoneSearchRequest xmlns:phs="http://clear.thomsonreuters.com/api/search/2.0">
      <PermissiblePurpose>
        <GLB>B</GLB>
        <DPPA>3</DPPA>
        <VOTER>7</VOTER>
      </PermissiblePurpose>
      <Reference>S2S Phone Search</Reference>
      <Criteria>
        <ph1:PhoneCriteria xmlns:ph1="com/thomsonreuters/schemas/search">
          <BusinessName>{escape_xml(business_name)}</BusinessName>
          <PersonName>
            <LastName>{escape_xml(last_name)}</LastName>
            <FirstName>{escape_xml(first_name)}</FirstName>
          </PersonName>
          <Address>
            <Street></Street>
            <City></City>
            <State></State>
            <ZipCode></ZipCode>
            <Province></Province>
            <Country></Country>
          </Address>
          <PhoneNumber></PhoneNumber>
        </ph1:PhoneCriteria>
      </Criteria>
      <Datasources>
        <PublicRecordPhones>true</PublicRecordPhones>
        <ReversePhoneLookup>true</ReversePhoneLookup>
      </Datasources>
      <PhonesDatasets>
        <BankAccountHeader>false</BankAccountHeader>
        <BusinessContactRecords>false</BusinessContactRecords>
        <BusinessPhones>false</BusinessPhones>
        <CanadianBusinessPhones>false</CanadianBusinessPhones>
        <CanadianPhones>false</CanadianPhones>
        <Experian>false</Experian>
        <DunBradstreet>false</DunBradstreet>
        <HouseholdListings>false</HouseholdListings>
        <PhoneRecords>false</PhoneRecords>
        <TransUnion>false</TransUnion>
        <Worldbase>false</Worldbase>
        <MotorVehicleServiceAndWarrantyRecords>false</MotorVehicleServiceAndWarrantyRecords>
        <MarijuanaRelatedBusinesses>false</MarijuanaRelatedBusinesses>
      </PhonesDatasets>
    </phs:PhoneSearchRequest>
    """

    headers = {
        "Content-Type": "application/xml",
        "Accept": "application/xml"
    }

    try:
        # Send POST request
        clear_post = requests_pkcs12.post(
            url,
            data=xml_body,
            headers=headers,
            auth=HTTPBasicAuth(username, password),
            pkcs12_filename=cert_path,
            pkcs12_password=cert_pass
        )

        if clear_post.status_code != 200:
            root = ET.fromstring(clear_post.text)
            error_message = root.find('.//Message').text if root.find('.//Message') is not None else "Unknown Error"
            return jsonify({'error': error_message}), clear_post.status_code

        # Parse the response to extract the URI
        root = ET.fromstring(clear_post.text)
        group_count_element = root.find('.//GroupCount')
        group_count = int(group_count_element.text) if group_count_element is not None else 0
        if group_count == 0:
            logging.info("No results found")
            return jsonify({"message": "No results found."}), 204

        uri = root.find('.//Uri').text

        # Fetch the results using the extracted URI
        get_results = requests_pkcs12.get(
            uri,
            headers={'Accept': 'application/xml'},
            auth=HTTPBasicAuth(username, password),
            pkcs12_filename=cert_path,
            pkcs12_password=cert_pass
        )

        if get_results.status_code != 200:
            return jsonify({'error': "Failed to fetch phone search results"}), get_results.status_code

        # Parse the results XML to extract phone numbers and relevance scores
        results_root = ET.fromstring(get_results.text)
        namespaces = {
            'ns2': 'com/thomsonreuters/schemas/search',
            'ns5': 'http://clear.thomsonreuters.com/api/search/2.0'
        }
        result_groups = results_root.findall('.//ResultGroup', namespaces)
        results = []

        for group in result_groups:
            relevance = group.find('.//Relevance').text
            dominant_values = group.find('.//DominantValues/ns2:PhoneDominantValues', namespaces)
            if dominant_values is not None:
                phone_number = dominant_values.find('.//PhoneNumber').text
                results.append({
                    "phone_number": phone_number,
                    "relevance": relevance
                })

        sorted_results = sorted(results, key=lambda x: x['relevance'], reverse=True)
        # Return the extracted data
        return jsonify(sorted_results), 200

    except Exception as e:
        logging.error(f"Post Request failed: {e}")
        return jsonify({'error': 'An Internal server error occurred'}), 500


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    serve(app, host='127.0.0.1', port=8080, threads=10)
