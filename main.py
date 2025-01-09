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


@app.route('/clear-search', methods=["POST"])
def search_clear():
    params = request.get_json()
    print(params)

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

        print(clear_post.status_code)
        print(clear_post.text)
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

        print(get_results.status_code)

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
