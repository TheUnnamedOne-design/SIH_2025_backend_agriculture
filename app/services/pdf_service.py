import os
import json
import zipfile
from datetime import datetime
from io import BytesIO
from typing import List, Tuple

from adobe.pdfservices.operation.auth.service_principal_credentials import ServicePrincipalCredentials
from adobe.pdfservices.operation.exception.exceptions import ServiceApiException, ServiceUsageException, SdkException
from adobe.pdfservices.operation.pdf_services_media_type import PDFServicesMediaType
from adobe.pdfservices.operation.io.cloud_asset import CloudAsset
from adobe.pdfservices.operation.io.stream_asset import StreamAsset
from adobe.pdfservices.operation.pdf_services import PDFServices
from adobe.pdfservices.operation.pdfjobs.jobs.extract_pdf_job import ExtractPDFJob
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_element_type import ExtractElementType
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_pdf_params import ExtractPDFParams
from adobe.pdfservices.operation.pdfjobs.result.extract_pdf_result import ExtractPDFResult

class PDFService:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    def extract_pdf_to_chunks(self, pdf_path: str, max_chars_per_chunk: int = 1200) -> Tuple[List[str], List[str]]:
        """
        Extracts text from PDF using Adobe PDF Services API job interface adapted from sample.
        Returns text chunks and chunk IDs for embedding pipelines.
        """
        try:
            with open(pdf_path, 'rb') as f:
                input_stream = f.read()

            credentials = ServicePrincipalCredentials(client_id=self.client_id, client_secret=self.client_secret)
            pdf_services = PDFServices(credentials=credentials)
            input_asset = pdf_services.upload(input_stream=input_stream, mime_type=PDFServicesMediaType.PDF)

            extract_pdf_params = ExtractPDFParams(elements_to_extract=[ExtractElementType.TEXT])
            extract_pdf_job = ExtractPDFJob(input_asset=input_asset, extract_pdf_params=extract_pdf_params)

            location = pdf_services.submit(extract_pdf_job)
            pdf_services_response = pdf_services.get_job_result(location, ExtractPDFResult)

            result_asset: CloudAsset = pdf_services_response.get_result().get_resource()
            stream_asset: StreamAsset = pdf_services.get_content(result_asset)

            # Read zip bytes in memory
            zip_bytes = stream_asset.get_input_stream()
            with zipfile.ZipFile(BytesIO(zip_bytes), 'r') as archive:
                with archive.open("structuredData.json") as jsonentry:
                    data = json.load(jsonentry)

            # Parse JSON to extract text blocks for chunking
            chunks = []
            chunk_ids = []
            base_name = os.path.basename(pdf_path)
            i = 0

            # Collect all text elements from the structured JSON recursively
            def collect_text(elements):
                texts = []
                for el in elements:
                    if "Text" in el and el["Text"].strip():
                        texts.append(el["Text"].strip())
                    if "Elements" in el:
                        texts.extend(collect_text(el["Elements"]))
                return texts

            text_elements = collect_text(data.get("elements", []))
            combined_text = "\n\n".join(text_elements)

            # Chunk combined text
            cur = combined_text
            while cur:
                chunk = cur[:max_chars_per_chunk]
                cur = cur[max_chars_per_chunk:]
                chunks.append(chunk)
                chunk_ids.append(f"{base_name}:chunk{i}")
                i += 1

            return chunks, chunk_ids

        except (ServiceApiException, ServiceUsageException, SdkException) as e:
            print(f"Adobe PDF Services API Exception: {e}")
            return [], []
