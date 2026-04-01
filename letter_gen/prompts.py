"""
Prompt templates for Explanation Letter V3 generation.
Embeds sample letter structures so the AI writes in the same style.
"""

# ---------------------------------------------------------------------------
# System prompt shared by all letter generation calls
# ---------------------------------------------------------------------------
LETTER_GEN_SYSTEM = """\
You are an expert immigration consultant and letter writer specialising in visa explanation letters.
You produce formal, persuasive letters in fluent English that follow the exact structure, tone, and level of detail shown in the reference samples.
Rules:
- Write ONLY the letter body (from header to signature). No commentary.
- Use facts from the JSON profile — NEVER fabricate or assume data.
- If a data field is null, skip that section gracefully.
- BE CONCISE AND SCANNABLE: Visa officers have limited time. Use short paragraphs and clear bullet points for lists of evidence. DO NOT write long, dense paragraphs or overly flowery language.
- AVOID REPETITION: Never repeat information (like itineraries or evidence) across multiple sections.
- Maintain a respectful, confident, and highly professional tone. No begging.
- Use specific numbers, dates, addresses — not vague statements.
- Output plain text (no markdown, no HTML tags).
"""

# ---------------------------------------------------------------------------
# Prompt 1: Explanation Letter WITHOUT refusal history
# Reference: "Explanation Letter for Australian Visitor Visa Application"
# ---------------------------------------------------------------------------
LETTER_NO_REFUSAL_PROMPT = """\
Write a Visa Explanation Letter for this applicant based on the JSON profile below.
CRITICAL INSTRUCTION: You MUST follow the EXACT structure, header format, section titles, and style of this REFERENCE LETTER (adapt content to the applicant's data). DO NOT use a generic letter template.

--- START REFERENCE LETTER ---
Explanation Letter for Australian Visitor Visa Application
Visitor Visa Application (Subclass 600 – Tourist stream)
Date: 31 March 2026
To: Department of Home Affairs Australian Government
Dear Visa Officer,

Applicant: Mrs. Ly Thi Hong (Date of birth: 10 June 1961)

I am writing to support my application for a Short Stay Visitor Visa (Subclass 600 – Tourist stream) and to confirm my genuine intention to visit Australia temporarily for tourism.

Purpose of Visit
I plan to visit Australia from 6 May 2026 to 15 May 2026 (11 days / 10 nights) purely for tourism. I will follow the attached detailed itinerary, staying only in confirmed hotels: The Social Hotel Sydney, Hyatt Centric Melbourne, and LyLo Brisbane. On 10 May and 11 May 2026, I will make two separate day visits by regional V/Line train to see my sister at 100 Hoopers Road, Kialla, Victoria, and will return to my hotel the same evening. I will not stay overnight at my sister's house.

Travel Arrangements
Return flight: Vietjet VJ85 (SGN–SYD) on 5 May 2026 and VJ86 (SYD–SGN) on 15 May 2026.
All hotels and domestic transfers are already booked. Full itinerary, flight tickets and hotel confirmations are attached.

Financial Capacity
I will fully self-fund the entire trip from my personal life savings in Vietnam. As a 64-year-old retiree with modest income, I have accumulated these savings over many years. As evidence, I have attached the Confirmation of Deposit Balances from BIDV Bank dated 30 March 2026 showing a term deposit of VND 200,000,000 (approximately USD 7,589). This amount is more than sufficient to cover all costs of this short 11-day trip (international flights, domestic flights, hotels, meals, local transport). I will not receive any financial support from my sister or any other person in Australia.

Strong Ties to Vietnam
I have very strong ties to Vietnam that guarantee my return:
- I am now 64 years old and my health is not strong, so I am not able to work or remain in Australia for any extended period.
- I have three adult children living in Vietnam. They are my strong family roots and the main reason I must return home after this short trip.
- I have my permanent registered residence and home in Long An province.
- I have stable savings and ongoing financial commitments in Vietnam.

Travel History
I have an excellent travel record. I previously visited Australia in 2008 and fully complied with all visa conditions. I have also travelled to Singapore, Thailand, Cambodia and Malaysia without any visa violations or overstays.

I declare that all information provided in this application is true and correct. I understand the visa conditions and will comply fully. I have no intention to work, study or remain in Australia beyond the authorised period.

Thank you for considering my application.

Yours sincerely,
Ly Thi Hong
Passport No: E00438172
Mobile: 0345529453
Address: Group 1, New Hamlet 1, My Hanh Nam Commune, Duc Hoa District, Long An Province, Viet Nam
--- END REFERENCE LETTER ---

**APPLICANT JSON PROFILE:**
{json_profile}

**ADDITIONAL CONTEXT (if any):**
{additional_context}

Write the letter now. Adapt the content to the applicant's destination country, visa type, and personal circumstances. Keep the same level of specificity and persuasive tone.

CRITICAL RULES:
1. COPY THE EXACT HEADER FORMAT: Start your letter exactly like the reference letter. DO NOT add the applicant's name, address, or phone number at the very top of the letter, because the reference letter does not have them there. 
2. BE CONCISE & USE BULLET POINTS: Write short, direct sentences. Use bullet points to list evidence, family members, or itinerary details so the visa officer can scan easily. Do not write long, overly formal filler text.
3. AVOID REPETITION: If you listed the itinerary in 'Purpose of Visit', do NOT repeat it in 'Travel Arrangements' or 'Strong Ties'.
4. FLEXIBLE SECTIONS: The reference letter is a GUIDE, not a rigid template. You MUST adapt based on the applicant's actual JSON data:
   - If the applicant HAS travel history → include a 'Travel History' section highlighting past compliance and timely returns.
   - If the applicant has NO travel history → either skip this section entirely OR write one short sentence acknowledging it.
   - If the applicant has additional strong evidence not in the reference (e.g., business ownership, property, sponsor) → mention it under the most relevant existing section.
   - Adapt section content to the applicant's destination country, visa type, and personal circumstances.
"""

# ---------------------------------------------------------------------------
# Prompt 2: Explanation Letter WITH refusal history mentioned
# Reference: "LETTER OF EXPLANATION" (Canada visa, mentions prior refusal)
# ---------------------------------------------------------------------------
LETTER_WITH_REFUSAL_PROMPT = """\
Write a Visa Explanation Letter for this applicant who has been PREVIOUSLY REFUSED a visa.
The letter must ACKNOWLEDGE the prior refusal(s) and explain why circumstances have changed.
CRITICAL INSTRUCTION: You MUST follow the EXACT structure, header format, section titles, and style of this REFERENCE LETTER (adapt content to the applicant's data). DO NOT use a generic letter template.

--- START REFERENCE LETTER ---
Letter of Explanation
BUI VAN THUY
Phan Dinh Thu Guesthouse, Group 5, Tan Phu Quarter, Tan Trieu Ward, Bien Hoa City, Dong Nai Province, Viet Nam
Email: BUIVANTHUY1979@GMAIL.COM
Date: 01 April 2026
To: Visa Officer
Department of Home Affairs, Australia
SUBJECT: Letter of Explanation for Visitor Visa Application – Tourism to Australia

Dear Visa Officer,

I respectfully submit this Letter of Explanation in support of my Visitor Visa (Subclass 600 – Tourist stream) application for a short tourism visit to Australia from 28 April 2026 to 03 May 2026.

I am a Vietnamese citizen (passport number E02321376, date of birth 20 October 1979). I acknowledge the previous refusal of my Australian Visitor visa on 10 October 2025. The refusal stated that I did not demonstrate a genuine intention to return to Viet Nam, my financial situation and employment were not convincing, and the purpose of the visit was not reasonable. I respect that decision and now provide clear evidence showing how my circumstances have changed.

Current Employment and Financial Situation
I am employed full-time as Foam Team Staff at Megasun Production Company Limited (continuous employment since March 2013; indefinite-term contract since 1 March 2023). I have approved leave for the exact trip dates (28 April–03 May 2026).

Key evidence addressing the prior refusal about finances and employment:
• Continuous employment over 13 years with indefinite-term contract and approved leave (company letter attached).
• Monthly salary of 12,000,000 VND with recent 6-month payslips.
• OCB term deposit of 300,000,000 VND (deposited 25 July 2025) with bank confirmation and 6-month statements showing regular salary credits.

Strong Family Ties and Commitments
I am married to TRAN THI PHUONG and have two dependent school-age children living in Viet Nam. I also own residential land and a registered vehicle.

Key evidence of strong home-country ties:
• Married to TRAN THI PHUONG; two dependent children — BUI THI VEN NHI (born 23 Sep 2007) and BUI THI THANH MAI (born 12 Jan 2016).
• Land Use Rights Certificate for residential land (114.6 m²) in Hong Son Commune, My Duc District, Ha Noi (issued 19 February 2025).
• 1.5-ton truck registered in my name (Registration 29Y-050.60).

Purpose of the Trip and Itinerary
The sole purpose is short-term tourism. I will follow the attached confirmed itinerary and return on the booked flights.

Planned itinerary summary (full bookings attached):
• 28 Apr 2026: Depart Viet Nam (Vietjet VJ145/VJ85)
• 29–30 Apr 2026: Sydney — Meriton Suites Kent Street
• 01–02 May 2026: Melbourne — Gordon House Apartments
• 03 May 2026: Return to Viet Nam (Vietjet VJ86/VJ194)
Duration: 6 days / 5 nights. All flights, hotels and travel medical insurance are confirmed and paid.

Travel History
I have previously travelled to Thailand (2019) and Japan (2022), complying fully with all visa conditions and returning on schedule each time. This demonstrates my respect for immigration rules and my pattern of genuine temporary visits.

Strong Ties and Intention to Return
I will return to Viet Nam on 03 May 2026 for these clear reasons:
• Long-term employment at Megasun (over 13 years) with approved leave only for the trip dates.
• Immediate family responsibilities to my spouse and two school-age children.
• Significant assets in Viet Nam: residential land and registered vehicle.
• Sufficient personal funds (OCB term deposit 300,000,000 VND) — no need to remain abroad.
These combined ties confirm my genuine temporary intent.

Supporting documents (attached)
• Megasun employment letter and approved leave
• Indefinite contract, 6 months payslips and bank statements
• OCB term deposit confirmation 300,000,000 VND (25 July 2025)
• Land Use Rights Certificate and vehicle registration
• Marriage certificate and children's birth certificates
• Confirmed flights, hotel bookings and paid travel insurance

Thank you for your consideration. I am available to provide any further documents or clarification required.

Sincerely,
BUI VAN THUY
Foam Team Staff, Megasun Production Company Limited
Email: BUIVANTHUY1979@GMAIL.COM
Phone: 0989303464
--- END REFERENCE LETTER ---

**APPLICANT JSON PROFILE:**
{json_profile}

**ADDITIONAL CONTEXT (if any):**
{additional_context}

Write the letter now. 
CRITICAL RULES:
1. COPY THE EXACT HEADER FORMAT: Start your letter exactly like the reference letter. DO NOT deviate from this layout.
2. NO NEW SECTIONS: DO NOT invent or add any new section headers that are not present in the reference letter.
3. MAP EVIDENCE TO REFUSAL REASONS: When you mention the prior refusal in the introduction, briefly state what the officer's concern was. Then, in the body sections, use bullet points to DIRECTLY MAP the new evidence to the previous refusal reasons (e.g., if previously refused for financial status, highlight the new savings explicitly as resolving that concern).
4. BE CONCISE & SCANNABLE: Use bullet points heavily. Keep paragraphs very short. Visa officers scan letters quickly.
5. AVOID REPETITION: Do not repeat the itinerary, refusal reasons, or evidence across multiple sections.
6. FLEXIBLE SECTIONS: The reference letter is a GUIDE, not a rigid template. You MUST adapt based on the applicant's actual JSON data:
   - If the applicant HAS travel history → include a 'Travel History' section highlighting compliance.
   - If the applicant has NO travel history → either skip this section entirely OR write one short sentence acknowledging it.
   - If the applicant has additional strong evidence not covered by the reference sections (e.g., business ownership, sponsor letter) → you MAY add a brief mention under the most relevant existing section. Do NOT create a new section header for it.
7. NATURAL CLOSING: Only the final 'Strong Ties and Intention to Return' section should end with a brief summary sentence (e.g., 'These combined ties confirm my genuine temporary intent.'). Do NOT add 'In summary' sentences to every section — keep the letter natural and human.
"""
# ---------------------------------------------------------------------------
# Prompt 3: Separate Refusal Explanation Letter
# Reference: "Explanation of Previous Australian Visa Refusals"
# ---------------------------------------------------------------------------
REFUSAL_EXPLANATION_PROMPT = """\
Write a SEPARATE document titled "Explanation of Previous Visa Refusals" for this applicant.
This is a standalone document that accompanies the main explanation letter.
Follow the EXACT structure and style of this REFERENCE LETTER (adapt content to the applicant's data):

--- START REFERENCE LETTER ---
Explanation of Previous Visa Refusals

Applicant: BUI VAN THUY
Date of Birth: 20 October 1979
Passport No.: E02321376
Date: 1 April 2026

Dear Visa Officer,

I am writing to provide a full explanation regarding the previous refusal of my visitor visa application.

Refusal
My previous application was refused on 10 October 2025. The recorded reason was that I did not demonstrate genuine intention to return to Viet Nam, my financial situation and employment were not convincing, and the purpose of the visit was not reasonable.

I fully respect that decision. Since then, I have submitted much stronger evidence to address each concern.

Changed circumstances and supporting evidence
• Official OCB confirmation of a term deposit of 300,000,000 VND (deposited 25 July 2025) together with 6-month bank statements.
• Indefinite employment contract with Megasun Production Company Limited (continuous employment since March 2013, over 13 years) and approved leave for 28 April – 03 May 2026.
• Land Use Rights Certificate for residential land (114.6 m²) in Hong Son Commune, My Duc District, Ha Noi (issued 19 February 2025).
• Vehicle registration certificate (1.5-ton truck, registration 29Y-050.60).
• Marriage certificate and birth certificates of my two dependent children.
• Full confirmed itinerary, hotel bookings and return flights (28 April – 03 May 2026).
• Travel medical insurance fully paid and submitted.

This short tourism trip is entirely self-funded from my personal savings and salary. I will depart on the approved date as shown on my return ticket and approved leave.

I respectfully submit that this additional evidence fully satisfies the core requirements for genuine temporary stay under the relevant immigration regulations. I ask you to consider this when assessing my current application.

Thank you for your time and consideration.

Sincerely,

BUI VAN THUY
Phone: 0989303464
--- END REFERENCE LETTER ---


**APPLICANT JSON PROFILE:**
{json_profile}

**ADDITIONAL CONTEXT (if any):**
{additional_context}

Write the refusal explanation document now. List EACH refusal with dates and reasons. Then bullet-point all changed circumstances. Keep it factual and concise.
"""
