"""
Multi-Brand Report Generator

This module provides functionality to generate reports for multiple brands
in either separate or consolidated format. It integrates with existing
report generation services and Brand Profile management.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Any, Tuple
import os
from pathlib import Path
import multiprocessing

from app.services.report_gen import ReportGenerator, ReportConfig, ReportData
from app.services.brand_profile import BrandProfileService, BrandProfileData
from app.services.brand_grouper import BrandGroupResult, BrandStatistics
from app.services.brand_ui_models import MultiBrandReportConfig, MultiBrandReportResult
from app.services.data_parser import CreatorRow

logger = logging.getLogger(__name__)


class MultiBrandReportGenerator:
    """
    Generates reports for multiple brands in separate or consolidated format.
    
    This class orchestrates the generation of multiple brand reports using
    the existing single-brand report generation infrastructure while adding
    multi-brand specific features like brand comparison and parallel processing.
    """
    
    def __init__(
        self,
        report_generator: ReportGenerator = None,
        brand_profile_service: BrandProfileService = None,
        pdf_renderer=None,
        ppt_renderer=None
    ):
        """
        Initialize MultiBrandReportGenerator.
        
        Args:
            report_generator: ReportGenerator instance for single-brand reports
            brand_profile_service: BrandProfileService for Brand Profile integration
            pdf_renderer: PDF renderer service
            ppt_renderer: PPT renderer service
        """
        self.report_generator = report_generator or ReportGenerator()
        self.brand_profile_service = brand_profile_service or BrandProfileService()
        self.pdf_renderer = pdf_renderer
        self.ppt_renderer = ppt_renderer
        
        # Configuration
        self.max_parallel_reports = 3  # Limit concurrent report generation
        self.reports_output_dir = "reports"
        
        # Parallel processing configuration
        self.max_workers = min(4, multiprocessing.cpu_count())  # Limit to 4 workers max
        self.enable_parallel_processing = True
        self.parallel_threshold = 3  # Use parallel processing for 3+ brands
        
        logger.info(f"MultiBrandReportGenerator initialized with {self.max_workers} max workers")
    
    def generate_reports(
        self,
        config: MultiBrandReportConfig,
        brand_group_result: BrandGroupResult,
        db_session
    ) -> MultiBrandReportResult:
        """
        Generate reports for selected brands.
        
        Args:
            config: Report generation configuration
            brand_group_result: Grouped creator data by brand
            db_session: Database session for Brand Profile access
            
        Returns:
            MultiBrandReportResult with generated report paths and status
        """
        logger.info(f"Starting multi-brand report generation for {len(config.selected_brands)} brands")
        
        result = MultiBrandReportResult(
            generated_reports={},
            failed_brands=[],
            generation_summary={},
            total_brands_processed=len(config.selected_brands)
        )
        
        try:
            if config.report_mode == "separate":
                # Generate separate reports for each brand
                generated_reports, failed_brands = self._generate_separate_reports(
                    config, brand_group_result, db_session
                )
                result.generated_reports = generated_reports
                result.failed_brands = failed_brands
                result.total_reports_generated = len(generated_reports)
                
                # Save multi-brand report record for separate reports
                if generated_reports:
                    try:
                        record_id = self._save_multi_brand_report_record(
                            config, {}, generated_reports, db_session
                        )
                        result.report_record_id = record_id
                    except Exception as e:
                        logger.warning(f"Failed to save multi-brand report record: {e}")
                
            elif config.report_mode == "consolidated":
                # Generate single consolidated report
                consolidated_path = self._generate_consolidated_report(
                    config, brand_group_result, db_session
                )
                if consolidated_path:
                    result.consolidated_report_path = consolidated_path
                    result.total_reports_generated = 1
                    
                    # Save multi-brand report record for consolidated report
                    try:
                        record_id = self._save_multi_brand_report_record(
                            config, {}, {"consolidated": consolidated_path}, db_session
                        )
                        result.report_record_id = record_id
                    except Exception as e:
                        logger.warning(f"Failed to save multi-brand report record: {e}")
                else:
                    result.success = False
                    result.failed_brands = [(brand, "Consolidated report generation failed") 
                                          for brand in config.selected_brands]
            
            else:
                raise ValueError(f"Unknown report mode: {config.report_mode}")
            
            # Generate summary
            result.generation_summary = self._generate_summary(
                config, brand_group_result, result
            )
            
            logger.info(f"Multi-brand report generation completed: "
                       f"{result.total_reports_generated} reports generated, "
                       f"{len(result.failed_brands)} failures")
            
            return result
            
        except Exception as e:
            logger.error(f"Multi-brand report generation failed: {e}")
            result.success = False
            result.failed_brands = [(brand, str(e)) for brand in config.selected_brands]
            return result
    
    def _generate_separate_reports(
        self,
        config: MultiBrandReportConfig,
        brand_group_result: BrandGroupResult,
        db_session
    ) -> tuple[Dict[str, str], List[tuple[str, str]]]:
        """
        Generate separate report for each selected brand with parallel processing.
        
        Args:
            config: Report generation configuration
            brand_group_result: Grouped creator data
            db_session: Database session
            
        Returns:
            Tuple of (generated_reports_dict, failed_brands_list)
        """
        start_time = time.time()
        generated_reports = {}
        failed_brands = []
        
        # Prepare tasks for parallel execution
        tasks = []
        for brand_name in config.selected_brands:
            if brand_name not in brand_group_result.brand_groups:
                failed_brands.append((brand_name, "Brand not found in grouped data"))
                continue
            
            creators = brand_group_result.brand_groups[brand_name]
            tasks.append((brand_name, creators))
        
        logger.info(f"Generating {len(tasks)} separate reports")
        
        # Determine if we should use parallel processing
        use_parallel = (
            self.enable_parallel_processing and 
            len(tasks) >= self.parallel_threshold and
            len(tasks) > 1
        )
        
        if use_parallel:
            logger.info(f"Using parallel processing with {min(self.max_workers, len(tasks))} workers")
            generated_reports, failed_brands = self._generate_reports_parallel(
                tasks, config, db_session, failed_brands
            )
        else:
            logger.info("Using sequential processing")
            generated_reports, failed_brands = self._generate_reports_sequential(
                tasks, config, db_session, failed_brands
            )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Separate reports generation completed in {elapsed_time:.2f}s: "
                   f"{len(generated_reports)} successful, {len(failed_brands)} failed")
        
        return generated_reports, failed_brands
    
    def _generate_reports_parallel(
        self,
        tasks: List[Tuple[str, List[CreatorRow]]],
        config: MultiBrandReportConfig,
        db_session,
        failed_brands: List[Tuple[str, str]]
    ) -> Tuple[Dict[str, str], List[Tuple[str, str]]]:
        """Generate reports in parallel using ThreadPoolExecutor."""
        generated_reports = {}
        
        # Use ThreadPoolExecutor for I/O bound report generation
        max_workers = min(self.max_workers, len(tasks))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_brand = {
                executor.submit(
                    self._generate_single_brand_report_safe,
                    brand_name, creators, config, db_session
                ): brand_name
                for brand_name, creators in tasks
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_brand):
                brand_name = future_to_brand[future]
                try:
                    result = future.result(timeout=300)  # 5 minute timeout per report
                    if result['success']:
                        generated_reports[brand_name] = result['file_path']
                        logger.info(f"Successfully generated report for brand: {brand_name}")
                    else:
                        failed_brands.append((brand_name, result['error']))
                        logger.error(f"Failed to generate report for brand {brand_name}: {result['error']}")
                except Exception as e:
                    failed_brands.append((brand_name, f"Parallel execution error: {str(e)}"))
                    logger.error(f"Parallel execution failed for brand {brand_name}: {e}")
        
        return generated_reports, failed_brands
    
    def _generate_reports_sequential(
        self,
        tasks: List[Tuple[str, List[CreatorRow]]],
        config: MultiBrandReportConfig,
        db_session,
        failed_brands: List[Tuple[str, str]]
    ) -> Tuple[Dict[str, str], List[Tuple[str, str]]]:
        """Generate reports sequentially."""
        generated_reports = {}
        
        for i, (brand_name, creators) in enumerate(tasks, 1):
            logger.info(f"Generating report {i}/{len(tasks)} for brand: {brand_name}")
            
            try:
                result = self._generate_single_brand_report_safe(brand_name, creators, config, db_session)
                if result['success']:
                    generated_reports[brand_name] = result['file_path']
                    logger.info(f"Successfully generated report for brand: {brand_name}")
                else:
                    failed_brands.append((brand_name, result['error']))
                    logger.error(f"Failed to generate report for brand {brand_name}: {result['error']}")
            except Exception as e:
                failed_brands.append((brand_name, f"Sequential execution error: {str(e)}"))
                logger.error(f"Sequential execution failed for brand {brand_name}: {e}")
        
        return generated_reports, failed_brands
    
    def _generate_single_brand_report_safe(
        self,
        brand_name: str,
        creators: List[CreatorRow],
        config: MultiBrandReportConfig,
        db_session
    ) -> Dict[str, Any]:
        """
        Thread-safe wrapper for single brand report generation.
        
        Returns:
            Dictionary with 'success', 'file_path', and 'error' keys
        """
        try:
            file_path = self._generate_single_brand_report(brand_name, creators, config, db_session)
            return {
                'success': True,
                'file_path': file_path,
                'error': None
            }
        except Exception as e:
            return {
                'success': False,
                'file_path': None,
                'error': str(e)
            }
                try:
                    report_path = future.result()
                    if report_path:
                        generated_reports[brand_name] = report_path
                        logger.info(f"Generated report for {brand_name}: {report_path}")
                    else:
                        failed_brands.append((brand_name, "Report generation returned None"))
                        
                except Exception as e:
                    logger.error(f"Failed to generate report for {brand_name}: {e}")
                    failed_brands.append((brand_name, str(e)))
        
        return generated_reports, failed_brands
    
    def _generate_single_brand_report(
        self,
        brand_name: str,
        creators: List[CreatorRow],
        config: MultiBrandReportConfig,
        db_session
    ) -> Optional[str]:
        """
        Generate a single brand report.
        
        Args:
            brand_name: Name of the brand
            creators: List of creators for this brand
            config: Report configuration
            db_session: Database session
            
        Returns:
            Path to generated report file or None if failed
        """
        try:
            # Get or create Brand Profile
            brand_profile = self._get_or_create_brand_profile(brand_name, db_session)
            
            # Create ReportConfig for this brand
            report_config = ReportConfig(
                brand_name=brand_name,
                batch_number=config.batch_number,
                period_start=date.fromisoformat(config.period_start),
                period_end=date.fromisoformat(config.period_end),
                # Add other config fields as needed
            )
            
            # Separate deal and non-deal rows (all creators are deals in multi-brand context)
            deal_rows = creators
            non_deal_rows = []
            
            # Generate report data
            report_data = self.report_generator.assemble_report_data(
                report_config, deal_rows, non_deal_rows, brand_profile
            )
            
            # Generate file paths
            safe_brand_name = self._sanitize_filename(brand_name)
            base_filename = f"{safe_brand_name}_{config.batch_number}_{self._generate_file_id()}"
            
            # Generate PDF and PPT files
            pdf_path = None
            ppt_path = None
            
            if self.pdf_renderer:
                pdf_filename = f"{base_filename}.pdf"
                pdf_path = os.path.join(self.reports_output_dir, pdf_filename)
                self.pdf_renderer.render(report_data, pdf_path)
            
            if self.ppt_renderer:
                ppt_filename = f"{base_filename}.pptx"
                ppt_path = os.path.join(self.reports_output_dir, ppt_filename)
                self.ppt_renderer.render(report_data, ppt_path)
            
            # Return the primary report path (PDF preferred)
            return pdf_path or ppt_path
            
        except Exception as e:
            logger.error(f"Failed to generate single brand report for {brand_name}: {e}")
            return None
    
    def _generate_consolidated_report(
        self,
        config: MultiBrandReportConfig,
        brand_group_result: BrandGroupResult,
        db_session
    ) -> Optional[str]:
        """
        Generate single consolidated report with all selected brands.
        
        Args:
            config: Report configuration
            brand_group_result: Grouped creator data
            db_session: Database session
            
        Returns:
            Path to consolidated report file or None if failed
        """
        try:
            logger.info("Generating consolidated multi-brand report")
            
            # Prepare individual brand reports data
            brand_reports = {}
            
            for brand_name in config.selected_brands:
                if brand_name not in brand_group_result.brand_groups:
                    logger.warning(f"Brand {brand_name} not found in grouped data")
                    continue
                
                creators = brand_group_result.brand_groups[brand_name]
                if not creators:
                    logger.warning(f"No creators found for brand {brand_name}")
                    continue
                
                # Get Brand Profile for this brand
                brand_profile = self._get_or_create_brand_profile(brand_name, db_session)
                
                # Create ReportConfig for this brand
                report_config = ReportConfig(
                    brand_name=brand_name,
                    batch_number=config.batch_number,
                    period_start=date.fromisoformat(config.period_start),
                    period_end=date.fromisoformat(config.period_end),
                )
                
                # Generate report data for this brand
                report_data = self.report_generator.assemble_report_data(
                    report_config, creators, [], brand_profile
                )
                
                brand_reports[brand_name] = report_data
            
            if not brand_reports:
                logger.warning("No valid brand reports to consolidate")
                return None
            
            # Prepare consolidated configuration
            consolidated_config = {
                'title': f"Multi-Brand Report ({len(brand_reports)} brands)",
                'batch_number': config.batch_number,
                'period_start': date.fromisoformat(config.period_start),
                'period_end': date.fromisoformat(config.period_end),
                'include_brand_comparison': config.include_brand_comparison,
                'next_plan': 'Fokus pada optimasi brand dengan performa terbaik dan perbaikan strategi untuk brand dengan konversi rendah.'
            }
            
            # Generate consolidated report file
            safe_filename = self._sanitize_filename(f"Consolidated_{config.batch_number}")
            base_filename = f"{safe_filename}_{self._generate_file_id()}"
            
            if self.pdf_renderer and hasattr(self.pdf_renderer, 'render_multi_brand'):
                # Use enhanced multi-brand PDF renderer
                pdf_filename = f"{base_filename}.pdf"
                pdf_path = os.path.join(self.reports_output_dir, pdf_filename)
                self.pdf_renderer.render_multi_brand(brand_reports, consolidated_config, pdf_path)
                return pdf_path
            elif self.pdf_renderer:
                # Fallback to regular PDF renderer with consolidated data
                logger.warning("Multi-brand PDF renderer not available, using fallback method")
                
                # Combine all creators for fallback method
                all_creators = []
                for creators in brand_reports.values():
                    all_creators.extend(creators.deal_rows)
                
                # Create consolidated Brand Profile
                consolidated_profile = self._create_consolidated_brand_profile(
                    config.selected_brands, db_session
                )
                
                # Create consolidated ReportConfig
                consolidated_brand_name = " + ".join(config.selected_brands)
                report_config = ReportConfig(
                    brand_name=consolidated_brand_name,
                    batch_number=config.batch_number,
                    period_start=date.fromisoformat(config.period_start),
                    period_end=date.fromisoformat(config.period_end),
                )
                
                # Generate consolidated report data
                report_data = self.report_generator.assemble_report_data(
                    report_config, all_creators, [], consolidated_profile
                )
                
                pdf_filename = f"{base_filename}.pdf"
                pdf_path = os.path.join(self.reports_output_dir, pdf_filename)
                self.pdf_renderer.render(report_data, pdf_path)
                
                # Also generate PPT if renderer available
                if self.ppt_renderer and hasattr(self.ppt_renderer, 'render_multi_brand'):
                    ppt_filename = f"{base_filename}.pptx"
                    ppt_path = os.path.join(self.reports_output_dir, ppt_filename)
                    self.ppt_renderer.render_multi_brand(brand_reports, consolidated_config, ppt_path)
                elif self.ppt_renderer:
                    ppt_filename = f"{base_filename}.pptx"
                    ppt_path = os.path.join(self.reports_output_dir, ppt_filename)
                    self.ppt_renderer.render(report_data, ppt_path)
                
                return pdf_path
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate consolidated report: {e}")
            return None
    
    def _get_or_create_brand_profile(
        self,
        brand_name: str,
        db_session
    ) -> BrandProfileData:
        """
        Get existing Brand Profile or create a new one.
        
        Args:
            brand_name: Name of the brand
            db_session: Database session
            
        Returns:
            BrandProfileData for the brand
        """
        try:
            return self.brand_profile_service.get_or_create(brand_name, db_session)
        except Exception as e:
            logger.warning(f"Failed to get/create Brand Profile for {brand_name}: {e}")
            # Return a default profile
            return BrandProfileData(name=brand_name)
    
    def _create_consolidated_brand_profile(
        self,
        brand_names: List[str],
        db_session
    ) -> BrandProfileData:
        """
        Create a consolidated Brand Profile combining data from multiple brands.
        
        Args:
            brand_names: List of brand names to consolidate
            db_session: Database session
            
        Returns:
            Consolidated BrandProfileData
        """
        consolidated_name = " + ".join(brand_names)
        consolidated_sku_list = []
        consolidated_sow = []
        
        for brand_name in brand_names:
            try:
                profile = self.brand_profile_service.get_by_name(brand_name, db_session)
                if profile:
                    # Add SKUs with brand prefix
                    for sku in profile.sku_list:
                        consolidated_sku_list.append(f"{brand_name}: {sku}")
                    
                    # Add SOW with brand header
                    if profile.sow:
                        consolidated_sow.append(f"**{brand_name}:**\n{profile.sow}")
                        
            except Exception as e:
                logger.warning(f"Failed to get profile for {brand_name}: {e}")
        
        return BrandProfileData(
            name=consolidated_name,
            sku_list=consolidated_sku_list,
            sow="\n\n".join(consolidated_sow)
        )
    
    def _generate_summary(
        self,
        config: MultiBrandReportConfig,
        brand_group_result: BrandGroupResult,
        result: MultiBrandReportResult
    ) -> Dict[str, Any]:
        """
        Generate summary information for the report generation process.
        
        Args:
            config: Report configuration
            brand_group_result: Grouped creator data
            result: Report generation result
            
        Returns:
            Summary dictionary
        """
        total_creators = sum(
            len(brand_group_result.brand_groups.get(brand, []))
            for brand in config.selected_brands
        )
        
        total_gmv = sum(
            brand_group_result.brand_statistics.get(brand, BrandStatistics("", 0, 0.0, 0.0, [], 0, 0.0)).total_gmv
            for brand in config.selected_brands
        )
        
        return {
            'report_mode': config.report_mode,
            'selected_brands': config.selected_brands,
            'total_creators_processed': total_creators,
            'total_gmv': total_gmv,
            'successful_reports': len(result.generated_reports),
            'failed_reports': len(result.failed_brands),
            'generation_timestamp': self._get_current_timestamp(),
            'batch_number': config.batch_number,
            'period': f"{config.period_start} to {config.period_end}"
        }
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for safe file system usage.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        import re
        # Remove or replace unsafe characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        sanitized = re.sub(r'\s+', '_', sanitized)  # Replace spaces with underscores
        return sanitized.strip('_')
    
    def _generate_file_id(self) -> str:
        """
        Generate a unique file ID for report files.
        
        Returns:
            Unique file ID string
        """
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _save_multi_brand_report_record(
        self,
        config: MultiBrandReportConfig,
        brand_reports: dict,
        report_paths: dict,
        db_session
    ) -> int:
        """
        Save multi-brand report record to database.
        
        Args:
            config: Report configuration
            brand_reports: Dict of brand reports
            report_paths: Dict of generated report paths
            db_session: Database session
            
        Returns:
            Report record ID
        """
        from app.models.db import ReportRecord
        import json
        
        # Determine primary brand name (for compatibility)
        primary_brand = config.selected_brands[0] if config.selected_brands else "Multi-Brand"
        
        # Create brand list JSON
        brand_list_json = json.dumps(config.selected_brands)
        
        # Get report paths
        pdf_path = None
        ppt_path = None
        
        if config.report_mode == "consolidated":
            # For consolidated reports, there should be one report file
            for path in report_paths.values():
                if path.endswith('.pdf'):
                    pdf_path = path
                elif path.endswith('.pptx'):
                    ppt_path = path
        else:
            # For separate reports, use the first report as primary (for compatibility)
            first_path = list(report_paths.values())[0] if report_paths else None
            if first_path:
                if first_path.endswith('.pdf'):
                    pdf_path = first_path
                    ppt_path = first_path.replace('.pdf', '.pptx')
                elif first_path.endswith('.pptx'):
                    ppt_path = first_path
                    pdf_path = first_path.replace('.pptx', '.pdf')
        
        # Create config snapshot
        config_snapshot = {
            "is_multi_brand": True,
            "report_mode": config.report_mode,
            "selected_brands": config.selected_brands,
            "brand_count": len(config.selected_brands),
            "batch_number": config.batch_number,
            "period_start": config.period_start,
            "period_end": config.period_end,
            "include_brand_comparison": config.include_brand_comparison,
            "generated_reports": report_paths
        }
        
        # Create report record
        record = ReportRecord(
            brand_name=primary_brand,
            batch_number=config.batch_number,
            period_start=date.fromisoformat(config.period_start),
            period_end=date.fromisoformat(config.period_end),
            pdf_path=pdf_path or "",
            ppt_path=ppt_path,
            config_snapshot=json.dumps(config_snapshot, ensure_ascii=False),
            is_multi_brand=True,
            brand_count=len(config.selected_brands),
            brand_list=brand_list_json,
            report_mode=config.report_mode
        )
        
        db_session.add(record)
        db_session.commit()
        db_session.refresh(record)
        
        return record.id
    
    def get_brand_profile_status_summary(
        self,
        brand_names: List[str],
        db_session
    ) -> Dict[str, str]:
        """
        Get profile status summary for multiple brands.
        
        Args:
            brand_names: List of brand names to check
            db_session: Database session
            
        Returns:
            Dictionary mapping brand names to status strings
        """
        status_summary = {}
        
        for brand_name in brand_names:
            try:
                profile = self.brand_profile_service.get_by_name(brand_name, db_session)
                if not profile:
                    status_summary[brand_name] = "missing"
                elif not profile.sku_list and not profile.sow:
                    status_summary[brand_name] = "empty"
                elif profile.sku_list and profile.sow:
                    status_summary[brand_name] = "complete"
                else:
                    status_summary[brand_name] = "partial"
                    
            except Exception as e:
                logger.warning(f"Failed to check profile status for {brand_name}: {e}")
                status_summary[brand_name] = "error"
        
        return status_summary