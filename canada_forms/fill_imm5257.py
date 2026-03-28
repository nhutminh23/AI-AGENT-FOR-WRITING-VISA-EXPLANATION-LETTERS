"""
Fill IMM5257E (Application for Visitor Visa) PDF form by updating XFA XML data.

Strategy: The template has an <xfa:data> section. We inject a complete form1 XML
structure matching the form's XFA field hierarchy, then write it back into the
cloned PDF.

The data structure was reverse-engineered from a correctly-filled reference PDF
where all checkboxes and fields render properly in Adobe Reader.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pypdf

from canada_forms.dial_codes import split_phone as _split_phone
from canada_forms.xml_helpers import (
    resolve_country as _resolve_country,
    resolve_marital as _resolve_marital,
    xml_escape as _e,
    yn as _yn,
    split_date as _split_date,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Build XFA XML matching reference PDF structure exactly
# ---------------------------------------------------------------------------

def _build_form1_xml(data: dict) -> str:
    """
    Build form1 XML matching the exact structure from the reference PDF.
    
    Key format rules discovered from reference:
    - Checkboxes: <ExclGroupName><ExclGroupName>Y</ExclGroupName></ExclGroupName>
    - Phone: NumberCountry=84 (no +), IntlNumber>IntlNumber=local, ActualNumber=+full
    - Address in ContactInformation > contact > AddressRow1/AddressRow2
    - Occupation rows in Occupation wrapper on Page3
    - BackgroundInfo/BackgroundInfo2 on Page3
    - BackgroundInfo3/Military/Occupation/GovPosition in PageWrapper
    - Signature with Consent0 > Choice in PageWrapper
    """
    today = date.today()
    L = []  # lines
    
    L.append('<form1>')
    
    # ================ PAGE 1 ================
    L.append('<Page1>')
    
    L.append('<PersonalDetails>')
    L.append(f'<UCIClientID>{_e(data.get("uci", ""))}</UCIClientID>')
    
    # ServiceIn (wrapped)
    L.append('<ServiceIn>')
    L.append(f'<ServiceIn>{_e(data.get("service_in", ""))}</ServiceIn>')
    L.append('</ServiceIn>')
    
    # VisaType (wrapped)
    L.append('<VisaType>')
    L.append(f'<VisaType>{_e(data.get("visa_type", "VisitorVisa"))}</VisaType>')
    L.append('</VisaType>')
    
    # Name (wrapped)
    L.append('<Name>')
    L.append(f'<FamilyName>{_e(data.get("family_name", ""))}</FamilyName>')
    L.append(f'<GivenName>{_e(data.get("given_name", ""))}</GivenName>')
    L.append('</Name>')
    
    # AliasName — indicator is double-wrapped
    has_alias = data.get("has_alias", "N")
    L.append('<AliasName>')
    L.append(f'<AliasFamilyName>{_e(data.get("alias_family_name", ""))}</AliasFamilyName>')
    L.append(f'<AliasGivenName>{_e(data.get("alias_given_name", ""))}</AliasGivenName>')
    L.append('<AliasNameIndicator>')
    L.append(f'<AliasNameIndicator>{_yn(has_alias)}</AliasNameIndicator>')
    L.append('</AliasNameIndicator>')
    L.append('</AliasName>')
    
    # Sex (wrapped)
    L.append('<Sex>')
    L.append(f'<Sex>{_e(data.get("sex", ""))}</Sex>')
    L.append('</Sex>')
    
    # DOB
    dob = data.get("dob", "")
    dob_y, dob_m, dob_d = _split_date(dob)
    L.append(f'<DOBYear>{dob_y}</DOBYear>')
    L.append(f'<DOBMonth>{dob_m}</DOBMonth>')
    L.append(f'<DOBDay>{dob_d}</DOBDay>')
    L.append(f'<PlaceBirthCity>{_e(data.get("birth_city", ""))}</PlaceBirthCity>')
    L.append(f'<PlaceBirthCountry>{_resolve_country(data.get("birth_country", ""))}</PlaceBirthCountry>')
    
    # Citizenship (wrapped)
    L.append('<Citizenship>')
    L.append(f'<Citizenship>{_resolve_country(data.get("citizenship", ""))}</Citizenship>')
    L.append('</Citizenship>')
    
    # CurrentCOR
    L.append('<CurrentCOR>')
    L.append('<Row2>')
    L.append(f'<Country>{_resolve_country(data.get("cor_country", ""))}</Country>')
    L.append(f'<Status>{_e(data.get("cor_status", ""))}</Status>')
    L.append(f'<Other/>')
    L.append(f'<FromDate/>')
    L.append(f'<ToDate/>')
    L.append('</Row2>')
    L.append('</CurrentCOR>')
    
    # PCRIndicator (Previous COR)
    L.append(f'<PCRIndicator>{_yn(data.get("has_prev_cor", "N"))}</PCRIndicator>')
    L.append('<PreviousCOR>')
    L.append('<Row2><Country/><Status/><Other/><FromDate/><ToDate/></Row2>')
    L.append('<Row3><Country/><Status/><Other/><FromDate/><ToDate/></Row3>')
    L.append('</PreviousCOR>')
    
    # SameAsCORIndicator
    L.append(f'<SameAsCORIndicator>{_yn(data.get("same_as_cor", "Y"))}</SameAsCORIndicator>')
    L.append('<CountryWhereApplying>')
    L.append('<Row2><Country/><Status/><Other/><FromDate/><ToDate/></Row2>')
    L.append('</CountryWhereApplying>')
    
    L.append('</PersonalDetails>')
    
    # MaritalStatus on Page1
    L.append('<MaritalStatus>')
    L.append('<SectionA>')
    L.append(f'<MaritalStatus>{_resolve_marital(data.get("marital_status", ""))}</MaritalStatus>')
    L.append(f'<DateOfMarriage>{_e(data.get("date_of_marriage", ""))}</DateOfMarriage>')
    # MarriageDate breakdown
    dom = data.get("date_of_marriage", "")
    dom_y, dom_m, dom_d = _split_date(dom)
    L.append('<MarriageDate>')
    L.append(f'<FromYr>{dom_y}</FromYr>')
    L.append(f'<FromMM>{dom_m.zfill(2) if dom_m else ""}</FromMM>')
    L.append(f'<FromDD>{dom_d.zfill(2) if dom_d else ""}</FromDD>')
    L.append('</MarriageDate>')
    L.append(f'<FamilyName>{_e(data.get("spouse_family_name", ""))}</FamilyName>')
    L.append(f'<GivenName>{_e(data.get("spouse_given_name", ""))}</GivenName>')
    L.append('</SectionA>')
    L.append('</MaritalStatus>')
    
    L.append('</Page1>')
    
    # ================ PAGE 2 ================
    L.append('<Page2>')
    
    # MaritalStatus > SectionA > PrevMarriedIndicator
    L.append('<MaritalStatus>')
    L.append('<SectionA>')
    L.append(f'<PrevMarriedIndicator>{_yn(data.get("prev_married", "N"))}</PrevMarriedIndicator>')
    L.append(f'<PMFamilyName>{_e(data.get("pm_family_name", ""))}</PMFamilyName>')
    L.append('<GivenName>')
    L.append(f'<PMGivenName>{_e(data.get("pm_given_name", ""))}</PMGivenName>')
    L.append('</GivenName>')
    L.append('<PrevSpouseDOB>')
    pm_dob = data.get("pm_dob", "")
    pm_y, pm_m, pm_d = _split_date(pm_dob)
    L.append(f'<DOBYear>{pm_y}</DOBYear>')
    L.append(f'<DOBMonth>{pm_m}</DOBMonth>')
    L.append(f'<DOBDay>{pm_d}</DOBDay>')
    L.append('</PrevSpouseDOB>')
    L.append(f'<TypeOfRelationship>{_e(data.get("pm_relationship", ""))}</TypeOfRelationship>')
    L.append(f'<FromDate>{_e(data.get("pm_from", ""))}</FromDate>')
    L.append('<ToDate>')
    L.append(f'<ToDate>{_e(data.get("pm_to", ""))}</ToDate>')
    L.append('</ToDate>')
    
    # Passport (inside SectionA per reference)
    L.append('<Passport>')
    L.append('<PassportNum>')
    L.append(f'<PassportNum>{_e(data.get("passport_number", ""))}</PassportNum>')
    L.append('</PassportNum>')
    L.append('<CountryofIssue>')
    L.append(f'<CountryofIssue>{_resolve_country(data.get("passport_country", ""))}</CountryofIssue>')
    L.append('</CountryofIssue>')
    L.append('<IssueDate>')
    L.append(f'<IssueDate>{_e(data.get("passport_issue_date", ""))}</IssueDate>')
    L.append('</IssueDate>')
    L.append(f'<ExpiryDate>{_e(data.get("passport_expiry_date", ""))}</ExpiryDate>')
    # Issue/Expiry date breakdowns
    pi = data.get("passport_issue_date", "")
    pi_y, pi_m, pi_d = _split_date(pi)
    L.append(f'<IssueYYYY>{pi_y}</IssueYYYY>')
    L.append(f'<IssueMM>{pi_m.zfill(2) if pi_m else ""}</IssueMM>')
    L.append(f'<IssueDD>{pi_d.zfill(2) if pi_d else ""}</IssueDD>')
    pe = data.get("passport_expiry_date", "")
    pe_y, pe_m, pe_d = _split_date(pe)
    L.append(f'<expiryYYYY>{pe_y}</expiryYYYY>')
    L.append(f'<expiryMM>{pe_m.zfill(2) if pe_m else ""}</expiryMM>')
    L.append(f'<expiryDD>{pe_d.zfill(2) if pe_d else ""}</expiryDD>')
    L.append('<TaiwanPIN/>')
    L.append('<IsraelPassportIndicator/>')
    L.append('</Passport>')
    
    # Languages
    L.append('<Languages>')
    L.append('<languages>')
    L.append('<nativeLang>')
    L.append(f'<nativeLang>{_e(data.get("native_language", ""))}</nativeLang>')
    L.append('</nativeLang>')
    L.append('<ableToCommunicate>')
    L.append(f'<ableToCommunicate>{_e(data.get("can_communicate", ""))}</ableToCommunicate>')
    L.append('</ableToCommunicate>')
    L.append('<lov/>')
    L.append('</languages>')
    L.append(f'<LanguageTest>{_yn(data.get("has_language_test", "N"))}</LanguageTest>')
    L.append('</Languages>')
    
    L.append('</SectionA>')
    L.append('</MaritalStatus>')
    
    # National ID
    nat_has = data.get("has_national_id", "N")
    L.append('<natID>')
    L.append('<q1>')
    L.append(f'<natIDIndicator>{_yn(nat_has)}</natIDIndicator>')
    L.append('</q1>')
    L.append('<natIDdocs>')
    L.append('<DocNum>')
    L.append(f'<DocNum>{_e(data.get("national_id_number", ""))}</DocNum>')
    L.append('</DocNum>')
    L.append('<CountryofIssue>')
    L.append(f'<CountryofIssue>{_resolve_country(data.get("national_id_country", ""))}</CountryofIssue>')
    L.append('</CountryofIssue>')
    L.append('<IssueDate>')
    L.append(f'<IssueDate>{_e(data.get("national_id_issue", ""))}</IssueDate>')
    L.append('</IssueDate>')
    L.append(f'<ExpiryDate>{_e(data.get("national_id_expiry", ""))}</ExpiryDate>')
    L.append('</natIDdocs>')
    L.append('</natID>')
    
    # US PR Card
    us_has = data.get("has_us_card", "N")
    L.append('<USCard>')
    L.append('<q1>')
    L.append(f'<usCardIndicator>{_yn(us_has)}</usCardIndicator>')
    L.append('</q1>')
    L.append('<usCarddocs>')
    L.append('<DocNum>')
    L.append(f'<DocNum>{_e(data.get("us_card_number", ""))}</DocNum>')
    L.append('</DocNum>')
    L.append(f'<ExpiryDate>{_e(data.get("us_card_expiry", ""))}</ExpiryDate>')
    L.append('</usCarddocs>')
    L.append('</USCard>')
    
    # Contact Information
    phone_number = data.get("phone_number", "")
    cc, local, full = _split_phone(phone_number)
    
    L.append('<ContactInformation>')
    L.append('<contact>')
    
    # AddressRow1 (mailing address)
    L.append('<AddressRow1>')
    L.append('<POBox>')
    L.append(f'<POBox>{_e(data.get("address_pobox", ""))}</POBox>')
    L.append('</POBox>')
    L.append('<Apt>')
    L.append(f'<AptUnit>{_e(data.get("address_apt", ""))}</AptUnit>')
    L.append('</Apt>')
    L.append('<StreetNum>')
    L.append(f'<StreetNum>{_e(data.get("address_street_num", ""))}</StreetNum>')
    L.append('</StreetNum>')
    L.append('<Streetname>')
    L.append(f'<Streetname>{_e(data.get("address_street_name", ""))}</Streetname>')
    L.append('</Streetname>')
    L.append('</AddressRow1>')
    
    # AddressRow2
    L.append('<AddressRow2>')
    L.append('<CityTow>')
    L.append(f'<CityTown>{_e(data.get("address_city", ""))}</CityTown>')
    L.append('</CityTow>')
    L.append('<Country>')
    L.append(f'<Country>{_resolve_country(data.get("address_country", ""))}</Country>')
    L.append('</Country>')
    L.append('<ProvinceState>')
    L.append(f'<ProvinceState>{_e(data.get("address_province", ""))}</ProvinceState>')
    L.append('</ProvinceState>')
    L.append('<PostalCode>')
    L.append(f'<PostalCode>{_e(data.get("address_postal_code", ""))}</PostalCode>')
    L.append('</PostalCode>')
    L.append(f'<District>{_e(data.get("address_district", ""))}</District>')
    L.append('</AddressRow2>')
    
    # SameAsMailingIndicator
    L.append(f'<SameAsMailingIndicator>{_yn(data.get("same_mailing_address", "Y"))}</SameAsMailingIndicator>')
    
    # ResidentialAddress (empty if same as mailing)
    L.append('<ResidentialAddressRow1>')
    L.append('<AptUnit><AptUnit/></AptUnit>')
    L.append('<StreetNum><StreetNum/></StreetNum>')
    L.append('<StreetName><Streetname/></StreetName>')
    L.append('<CityTown><CityTown/></CityTown>')
    L.append('</ResidentialAddressRow1>')
    L.append('<ResidentialAddressRow2>')
    L.append('<Country><Country/></Country>')
    L.append('<ProvinceState><ProvinceState/></ProvinceState>')
    L.append('<PostalCode><PostalCode/></PostalCode>')
    L.append('<District/>')
    L.append('</ResidentialAddressRow2>')
    
    # Phone Numbers
    L.append('<PhoneNumbers>')
    L.append('<Phone>')
    L.append(f'<Type>{_e(data.get("phone_type", "02"))}</Type>')
    L.append('<CanadaUS>0</CanadaUS>')
    L.append('<Other>1</Other>')
    L.append('<NumberExt/>')
    L.append(f'<NumberCountry>{cc}</NumberCountry>')
    L.append(f'<ActualNumber>{full}</ActualNumber>')
    L.append('<NANumber><AreaCode/><FirstThree/><LastFive/></NANumber>')
    L.append('<IntlNumber>')
    L.append(f'<IntlNumber>{local}</IntlNumber>')
    L.append('</IntlNumber>')
    L.append('</Phone>')
    
    # Alt phone
    alt_phone = data.get("alt_phone", "")
    alt_cc, alt_local, alt_full = _split_phone(alt_phone)
    L.append('<AltPhone>')
    L.append(f'<Type>{_e(data.get("alt_phone_type", ""))}</Type>')
    L.append('<CanadaUS>0</CanadaUS>')
    L.append(f'<Other>{"1" if alt_phone else "0"}</Other>')
    L.append('<NumberExt/>')
    L.append(f'<NumberCountry>{alt_cc}</NumberCountry>')
    L.append(f'<ActualNumber>{alt_full}</ActualNumber>')
    L.append('<NANumber><AreaCode/><FirstThree/><LastFive/></NANumber>')
    L.append('<IntlNumber>')
    L.append(f'<IntlNumber>{alt_local}</IntlNumber>')
    L.append('</IntlNumber>')
    L.append('</AltPhone>')
    L.append('</PhoneNumbers>')
    
    # Fax/Email
    L.append('<FaxEmail>')
    L.append('<Phone><CanadaUS>0</CanadaUS><Other>0</Other><NumberExt/><NumberCountry/><ActualNumber/>')
    L.append('<NANumber><AreaCode/><FirstThree/><LastFive/></NANumber>')
    L.append('<IntlNumber><IntlNumber/></IntlNumber></Phone>')
    L.append(f'<Email>{_e(data.get("email", ""))}</Email>')
    L.append('</FaxEmail>')
    
    L.append('</contact>')
    L.append('</ContactInformation>')
    
    L.append('</Page2>')
    
    # ================ PAGE 3 ================
    L.append('<Page3>')
    
    # Details of Visit
    L.append('<DetailsOfVisit>')
    L.append('<PurposeRow1>')
    L.append('<PurposeOfVisit>')
    L.append(f'<PurposeOfVisit>{_e(data.get("purpose", ""))}</PurposeOfVisit>')
    L.append('</PurposeOfVisit>')
    # Only fill "Other" description when purpose is '07' (Other)
    purpose_val = data.get('purpose', '')
    other_text = data.get('purpose_other', '') if purpose_val == '07' else ''
    L.append('<Other>')
    L.append(f'<Other>{_e(other_text)}</Other>')
    L.append('</Other>')
    L.append('<HowLongStay>')
    L.append(f'<FromDate>{_e(data.get("travel_from", ""))}</FromDate>')
    L.append(f'<ToDate>{_e(data.get("travel_to", ""))}</ToDate>')
    # StayDates breakdown
    tf = data.get("travel_from", "")
    tf_y, tf_m, tf_d = _split_date(tf)
    tt = data.get("travel_to", "")
    tt_y, tt_m, tt_d = _split_date(tt)
    L.append('<StayDates>')
    L.append(f'<FromYr>{tf_y}</FromYr><FromMM>{tf_m.zfill(2) if tf_m else ""}</FromMM><FromDD>{tf_d.zfill(2) if tf_d else ""}</FromDD>')
    L.append(f'<ToYr>{tt_y}</ToYr><ToMM>{tt_m.zfill(2) if tt_m else ""}</ToMM><ToDD>{tt_d.zfill(2) if tt_d else ""}</ToDD>')
    L.append('</StayDates>')
    L.append('</HowLongStay>')
    L.append('<Funds>')
    L.append(f'<Funds>{_e(data.get("funds", ""))}</Funds>')
    L.append('</Funds>')
    L.append('</PurposeRow1>')
    
    # Contacts in Canada
    L.append('<Contacts_Row1>')
    L.append('<Name>')
    L.append(f'<Name>{_e(data.get("contact1_name", ""))}</Name>')
    L.append('</Name>')
    L.append('<RelationshipToMe>')
    L.append(f'<RelationshipToMe>{_e(data.get("contact1_relationship", ""))}</RelationshipToMe>')
    L.append('</RelationshipToMe>')
    L.append('<AddressInCanada>')
    L.append(f'<AddressInCanada>{_e(data.get("contact1_address", ""))}</AddressInCanada>')
    L.append('</AddressInCanada>')
    L.append('</Contacts_Row1>')
    L.append('</DetailsOfVisit>')
    
    # Contact Row 2 (at Page3 level, not inside DetailsOfVisit per reference)
    L.append('<Contacts_Row2>')
    L.append('<Name>')
    L.append(f'<Name>{_e(data.get("contact2_name", ""))}</Name>')
    L.append('</Name>')
    L.append('<Relationship>')
    L.append(f'<RelationshipToMe>{_e(data.get("contact2_relationship", ""))}</RelationshipToMe>')
    L.append('</Relationship>')
    L.append('<AddressInCanada>')
    L.append(f'<AddressInCanada>{_e(data.get("contact2_address", ""))}</AddressInCanada>')
    L.append('</AddressInCanada>')
    L.append('</Contacts_Row2>')
    
    # Education
    has_edu = data.get("has_education", "N")
    L.append('<Education>')
    L.append(f'<EducationIndicator>{_yn(has_edu)}</EducationIndicator>')
    edu = data.get("education", {}) if has_edu == "Y" else {}
    L.append('<Edu_Row1>')
    L.append(f'<FromYear>{_e(edu.get("from_year", ""))}</FromYear>')
    L.append(f'<FromMonth>{_e(edu.get("from_month", ""))}</FromMonth>')
    L.append(f'<ToYear>{_e(edu.get("to_year", ""))}</ToYear>')
    L.append(f'<ToMonth>{_e(edu.get("to_month", ""))}</ToMonth>')
    L.append(f'<FieldOfStudy>{_e(edu.get("field", ""))}</FieldOfStudy>')
    L.append(f'<School>{_e(edu.get("school", ""))}</School>')
    L.append(f'<CityTown>{_e(edu.get("city", ""))}</CityTown>')
    L.append('<Country>')
    L.append(f'<Country>{_resolve_country(edu.get("country", ""))}</Country>')
    L.append('</Country>')
    L.append(f'<ProvState>{_e(edu.get("province", ""))}</ProvState>')
    L.append('</Edu_Row1>')
    L.append('</Education>')
    
    # Occupation (wrapped in parent <Occupation>)
    L.append('<Occupation>')
    for i in range(3):
        occ = data.get(f"occupation_{i}", {})
        if not occ and i == 0:
            occ = data.get("current_occupation", {})
        L.append(f'<OccupationRow{i+1}>')
        if occ:
            L.append(f'<FromYear>{_e(occ.get("from_year", ""))}</FromYear>')
            L.append(f'<FromMonth>{_e(occ.get("from_month", ""))}</FromMonth>')
            L.append(f'<ToYear>{_e(occ.get("to_year", ""))}</ToYear>')
            L.append(f'<ToMonth>{_e(occ.get("to_month", ""))}</ToMonth>')
            L.append('<Occupation>')
            L.append(f'<Occupation>{_e(occ.get("title", ""))}</Occupation>')
            L.append('</Occupation>')
            L.append(f'<Employer>{_e(occ.get("employer", ""))}</Employer>')
            L.append('<CityTown>')
            L.append(f'<CityTown>{_e(occ.get("city", ""))}</CityTown>')
            L.append('</CityTown>')
            L.append('<Country>')
            L.append(f'<Country>{_resolve_country(occ.get("country", ""))}</Country>')
            L.append('</Country>')
            L.append(f'<ProvState>{_e(occ.get("province", ""))}</ProvState>')
        else:
            L.append('<FromYear/><FromMonth/><ToYear/><ToMonth/>')
            L.append('<Occupation><Occupation/></Occupation>')
            L.append('<Employer/><CityTown><CityTown/></CityTown>')
            L.append('<Country><Country/></Country><ProvState/>')
        L.append(f'</OccupationRow{i+1}>')
    L.append('</Occupation>')
    
    # BackgroundInfo (Q1: medical)
    L.append('<BackgroundInfo>')
    L.append(f'<Choice>{_yn(data.get("bg_medical", "N"))}</Choice>')
    L.append(f'<Choice>{_yn(data.get("bg_medical_b", data.get("bg_medical", "N")))}</Choice>')
    L.append('<Details>')
    L.append(f'<MedicalDetails>{_e(data.get("bg_medical_details", ""))}</MedicalDetails>')
    L.append('</Details>')
    L.append('</BackgroundInfo>')
    
    # BackgroundInfo2 (Q2: visa refused) — on Page3 per reference
    L.append('<BackgroundInfo2>')
    L.append(f'<VisaChoice1>{_yn(data.get("bg_overstayed", "N"))}</VisaChoice1>')
    L.append(f'<VisaChoice2>{_yn(data.get("bg_refused_visa", data.get("bg_refused_entry", "N")))}</VisaChoice2>')
    L.append('<Details>')
    L.append(f'<refusedDetails>{_e(data.get("bg_refused_details", ""))}</refusedDetails>')
    L.append(f'<VisaChoice3>{_yn(data.get("bg_applied_before", "N"))}</VisaChoice3>')
    L.append('</Details>')
    L.append('</BackgroundInfo2>')
    
    # PageWrapper: BackgroundInfo3, Military, Occupation, GovPosition, Signature
    L.append('<PageWrapper>')
    
    # BackgroundInfo3 (Q3: crime)
    L.append('<BackgroundInfo3>')
    L.append(f'<Choice>{_yn(data.get("bg_crime", "N"))}</Choice>')
    L.append(f'<details>{_e(data.get("bg_crime_details", ""))}</details>')
    L.append('</BackgroundInfo3>')
    
    # Military (Q4)
    L.append('<Military>')
    L.append(f'<Choice>{_yn(data.get("bg_military", "N"))}</Choice>')
    L.append(f'<militaryServiceDetails>{_e(data.get("bg_military_details", ""))}</militaryServiceDetails>')
    L.append('</Military>')
    
    # Occupation > Choice (Q5: political)
    L.append('<Occupation>')
    L.append(f'<Choice>{_yn(data.get("bg_political", "N"))}</Choice>')
    L.append('</Occupation>')
    
    # GovPosition > Choice (Q6: witnessed)
    L.append('<GovPosition>')
    L.append(f'<Choice>{_yn(data.get("bg_witnessed", "N"))}</Choice>')
    L.append('</GovPosition>')
    
    L.append('</PageWrapper>')
    
    # Signature
    L.append('<Signature>')
    L.append('<Consent0>')
    L.append('<Choice>Y</Choice>')
    L.append('</Consent0>')
    L.append(f'<C1CertificateIssueDate>{today.isoformat()}</C1CertificateIssueDate>')
    L.append('</Signature>')
    
    L.append('</Page3>')
    
    L.append('</form1>')
    
    return '\n'.join(L)


# ---------------------------------------------------------------------------
# Main fill function
# ---------------------------------------------------------------------------

def fill_imm5257(
    data: dict,
    template_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Fill IMM5257E PDF by injecting XFA form data."""
    template_path = Path(template_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(str(template_path))
    if reader.is_encrypted:
        reader.decrypt("")

    writer = pypdf.PdfWriter(clone_from=reader)

    acroform_ref = writer._root_object.get("/AcroForm")
    if not acroform_ref:
        raise RuntimeError("PDF has no AcroForm")

    acroform = acroform_ref.get_object() if hasattr(acroform_ref, "get_object") else acroform_ref
    xfa_ref = acroform.get("/XFA")
    if not xfa_ref:
        raise RuntimeError("PDF has no XFA data")

    xfa_array = xfa_ref.get_object() if hasattr(xfa_ref, "get_object") else xfa_ref

    datasets_idx = None
    for i, item in enumerate(xfa_array):
        resolved = item.get_object() if hasattr(item, "get_object") else item
        if str(resolved) == "datasets":
            datasets_idx = i + 1
            break

    if datasets_idx is None:
        raise RuntimeError("Could not find 'datasets' in XFA array")

    datasets_stream_ref = xfa_array[datasets_idx]
    datasets_stream = datasets_stream_ref.get_object() if hasattr(datasets_stream_ref, "get_object") else datasets_stream_ref

    original_xml = datasets_stream.get_data().decode("utf-8", errors="replace")
    form1_xml = _build_form1_xml(data)

    # Strategy: find the <xfa:data ...> opening and its closing tag, then replace
    # the content between them. Must handle newlines inside tags (common in XFA).
    # Look for '<xfa:data' that's NOT '<xfa:datasets'
    data_start = -1
    search_from = 0
    while True:
        idx = original_xml.find('<xfa:data', search_from)
        if idx == -1:
            break
        # Make sure it's not <xfa:datasets
        after = original_xml[idx + 9:]  # after '<xfa:data'
        if after and (after[0] in (' ', '\n', '\r', '>', '/')):
            data_start = idx
            break
        search_from = idx + 10

    if data_start == -1:
        raise RuntimeError("No <xfa:data> element found in datasets XML")

    # Find the > that closes the opening tag
    open_end = original_xml.find('>', data_start + 9)
    if open_end == -1:
        raise RuntimeError("Malformed <xfa:data> tag")

    is_self_closing = original_xml[open_end - 1] == '/'
    if is_self_closing:
        # Self-closing: <xfa:data ... /> → replace with open + content + close
        updated_xml = (
            original_xml[:data_start]
            + '<xfa:data xfa:dataNode="dataGroup">\n'
            + form1_xml + '\n'
            + '</xfa:data>'
            + original_xml[open_end + 1:]
        )
    else:
        # Find </xfa:data with optional whitespace before >
        close_pattern = '</xfa:data'
        close_idx = original_xml.find(close_pattern, open_end)
        if close_idx == -1:
            raise RuntimeError("No closing </xfa:data> found")
        # Find the > after </xfa:data
        close_end = original_xml.find('>', close_idx + len(close_pattern))
        if close_end == -1:
            raise RuntimeError("Malformed </xfa:data> tag")

        # Replace everything between opening > and </xfa:data...>
        updated_xml = (
            original_xml[:open_end + 1]
            + '\n' + form1_xml + '\n'
            + original_xml[close_idx:close_end + 1]
            + original_xml[close_end + 1:]
        )

    datasets_stream.set_data(updated_xml.encode("utf-8"))

    filled_count = sum(1 for v in data.values() if v not in (None, "", "0", False, {}))

    # NOTE: Do NOT call writer.encrypt() here!
    # The template contains a DocMDP digital signature (in /Perms) that IRCC
    # validates on upload. Re-encrypting with new keys invalidates this signature.
    # clone_from preserves the /Perms dict with the original signature.
    # After filling, user must open PDF in Adobe Reader → click Validate → Save
    # to restore proper encryption and generate upload barcodes.

    with open(output_path, "wb") as f:
        writer.write(f)

    logger.info("IMM5257E XFA filled: %d fields -> %s", filled_count, output_path)
    return output_path
