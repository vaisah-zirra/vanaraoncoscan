USEFUL_PARTS = [('AI', 'AI image analysis and assessment of suspicious findings'), ('Images', 'Highlighted areas and image annotations'), ('Quality', 'Image-quality checks'), ('Review', 'Specialist review and recommendations'), ('Report', 'Downloadable case report'), ('Care', 'Referral and follow-up coordination'), ('None', 'None yet'), ('Other', 'Other')]
ADOPTION_FACTORS = [('Evidence', 'Clinical accuracy and supporting evidence'), ('Cost', 'Cost and affordability'), ('Integration', 'Compatibility with existing systems'), ('Training', 'Ease of use and staff training'), ('Privacy', 'Data privacy and security'), ('Infrastructure', 'Internet, equipment and technical requirements'), ('Regulation', 'Clinical accountability and regulatory approval'), ('Support', 'Technical support and reliability'), ('Other', 'Other'), ('Unsure', 'Not sure yet')]
FACTOR_LABELS = dict(ADOPTION_FACTORS, Governance='Data governance and approvals (earlier response)', None_='No barrier identified yet (earlier response)')
FACTOR_LABELS['None'] = FACTOR_LABELS.pop('None_')
def factor_counts(responses):
    from collections import Counter
    counts = Counter()
    for response in responses:
        counts.update(set(response.barriers or ([response.barrier] if response.barrier else [])))
    return [{'barrier': FACTOR_LABELS.get(code, code), 'n': count} for code, count in counts.most_common()]
