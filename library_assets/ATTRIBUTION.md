# Ultrasound sample attribution

Vallez, Noelia; Bueno, Gloria; Deniz, Oscar; Rienda, Miguel Angel; Pastor, Carlos (2025). **BUS-UCLM: Breast ultrasound lesion segmentation dataset**, version 3. Mendeley Data. https://doi.org/10.17632/7fvgj4jsp7.3

License: Creative Commons Attribution 4.0 International, https://creativecommons.org/licenses/by/4.0/ . The publisher's version-3 page explicitly lists CC BY 4.0 (verified 25 September 2026).

Four original PNG files are redistributed here. Pixel data is unchanged. Filenames are renamed for neutral display; original filenames, source download URLs and SHA-256 checksums are in manifest.json. No visible patient names or identifiers were observed in the selected images. Scanner annotations remain as supplied.

The images are sample assets, not images of the named fictional patients. They are not assigned diagnostic labels by this import. The existing authored case scenarios are separate workflow fixtures, not validated interpretations of these images. A later assessment engine must keep that distinction explicit and verify image/scenario suitability.

The application displays attribution in the upload page's Image source & licence section. Include this notice with redistributed assets and future exports containing them.


## Assessment annotations and quality sample

Sample 05 adds CHCO_000.png from BUS-UCLM V3 under the same CC BY 4.0 terms. Published matching masks for samples 01–05 are retained under masks/. Bounding rectangles are computed from the non-black mask pixels; profile metadata records mask filenames, download URLs and verified hashes. The displayed rectangles are derived annotations; the image pixels remain unchanged. No heatmap or confidence score is fabricated.

Sample 06 is the unmodified 95 × 75 pixel BMP at originals/benign/us1.bmp from Rodrigues, Paulo Sergio (2017), “Breast Ultrasound Image”, Mendeley Data V1, DOI: https://doi.org/10.17632/wmy84gzngw.1 . License: https://creativecommons.org/licenses/by/4.0/ . The source ZIP hash is 87dbd3aaa89e2d8886839983be3a985b7b190d5d8cb167d95a8dcd5d224b63f7. Its original pixels and format are preserved; only the display filename changes. The technical prototype policy requires at least 128 pixels on each side. This is not a validated clinical threshold.

Assessment responses are predefined. Source mask labels support the suspicious and non-suspicious examples; sample 04 deliberately exercises the uncertain workflow despite its benign source label. The uncertainty is not a measured model output. Profiles and source-derived annotations are stored with each completed assessment so later library changes do not rewrite the record.
