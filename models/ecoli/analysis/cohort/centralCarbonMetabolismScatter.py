"""
Central carbon metabolism comparison to Toya et al

@organization: Covert Lab, Department of Bioengineering, Stanford University
@date: Created 4/3/17
"""

from __future__ import absolute_import

import os
import cPickle
import re

import numpy as np
from matplotlib import pyplot as plt
from scipy.stats import pearsonr

from models.ecoli.analysis.AnalysisPaths import AnalysisPaths
from wholecell.io.tablereader import TableReader
from wholecell.utils import units
from wholecell.utils.sparkline import whitePadSparklineAxis
from wholecell.analysis.analysis_tools import exportFigure

from models.ecoli.processes.metabolism import COUNTS_UNITS, VOLUME_UNITS, TIME_UNITS, MASS_UNITS
from models.ecoli.analysis import cohortAnalysisPlot


class Plot(cohortAnalysisPlot.CohortAnalysisPlot):
	def do_plot(self, variantDir, plotOutDir, plotOutFileName, simDataFile, validationDataFile, metadata):
		if not os.path.isdir(variantDir):
			raise Exception, "variantDir does not currently exist as a directory"

		if not os.path.exists(plotOutDir):
			os.mkdir(plotOutDir)

		# Get all cells
		ap = AnalysisPaths(variantDir, cohort_plot = True)
		allDir = ap.get_cells()

		validation_data = cPickle.load(open(validationDataFile, "rb"))
		toyaReactions = validation_data.reactionFlux.toya2010fluxes["reactionID"]
		toyaFluxes = validation_data.reactionFlux.toya2010fluxes["reactionFlux"]
		toyaStdev = validation_data.reactionFlux.toya2010fluxes["reactionFluxStdev"]
		toyaFluxesDict = dict(zip(toyaReactions, toyaFluxes))
		toyaStdevDict = dict(zip(toyaReactions, toyaStdev))

		sim_data = cPickle.load(open(simDataFile))
		cellDensity = sim_data.constants.cellDensity

		modelFluxes = {}
		toyaOrder = []
		for rxn in toyaReactions:
			modelFluxes[rxn] = []
			toyaOrder.append(rxn)

		for simDir in allDir:
			simOutDir = os.path.join(simDir, "simOut")

			try:
				massListener = TableReader(os.path.join(simOutDir, "Mass"))
				cellMass = massListener.readColumn("cellMass")
				dryMass = massListener.readColumn("dryMass")
				massListener.close()
			except Exception as e:
				print(e)
				continue

			# skip if no data
			if cellMass.shape is ():
				continue

			coefficient = dryMass / cellMass * cellDensity.asNumber(MASS_UNITS / VOLUME_UNITS)

			fbaResults = TableReader(os.path.join(simOutDir, "FBAResults"))
			reactionIDs = np.array(fbaResults.readAttribute("reactionIDs"))
			reactionFluxes = (COUNTS_UNITS / MASS_UNITS / TIME_UNITS) * (fbaResults.readColumn("reactionFluxes").T / coefficient).T
			fbaResults.close()

			for toyaReaction in toyaReactions:
				fluxTimeCourse = []

				for rxn in reactionIDs:
					if re.findall(toyaReaction, rxn):
						reverse = 1
						if re.findall("(reverse)", rxn):
							reverse = -1

						if len(fluxTimeCourse):
							fluxTimeCourse += reverse * reactionFluxes[:, np.where(reactionIDs == rxn)]
						else:
							fluxTimeCourse = reverse * reactionFluxes[:, np.where(reactionIDs == rxn)]

				if len(fluxTimeCourse):
					modelFluxes[toyaReaction].append(np.mean(fluxTimeCourse).asNumber(units.mmol / units.g / units.h))

		toyaVsReactionAve = []
		rxn_order = []
		for rxn, toyaFlux in toyaFluxesDict.iteritems():
			rxn_order.append(rxn)
			if rxn in modelFluxes:
				toyaVsReactionAve.append((np.mean(modelFluxes[rxn]), toyaFlux.asNumber(units.mmol / units.g / units.h), np.std(modelFluxes[rxn]), toyaStdevDict[rxn].asNumber(units.mmol / units.g / units.h)))

		outlier_indicies = np.zeros(len(toyaReactions), bool)
		outlier_indicies[rxn_order.index('SUCCINATE-DEHYDROGENASE-UBIQUINONE-RXN-SUC/UBIQUINONE-8//FUM/CPD-9956.31.')] = True
		outlier_indicies[rxn_order.index('ISOCITDEH-RXN')] = True

		toyaVsReactionAve = np.array(toyaVsReactionAve)
		rWithAll = pearsonr(toyaVsReactionAve[:,0], toyaVsReactionAve[:,1])
		rWithoutOutliers = pearsonr(toyaVsReactionAve[~outlier_indicies,0], toyaVsReactionAve[~outlier_indicies,1])

		plt.figure(figsize = (3.5, 3.5))
		ax = plt.axes()
		plt.title("Central Carbon Metabolism Flux, Pearson R = %.4f, p = %s\n(%.4f, %s without outliers)" % (rWithAll[0], rWithAll[1], rWithoutOutliers[0], rWithoutOutliers[1]), fontsize = 6)
		plt.errorbar(toyaVsReactionAve[:,1], toyaVsReactionAve[:,0], xerr = toyaVsReactionAve[:,3], yerr = toyaVsReactionAve[:,2], fmt = "none", ecolor = "k", alpha = 0.5, linewidth = 0.5)
		ylim = plt.ylim()
		plt.plot([ylim[0], ylim[1]], [ylim[0], ylim[1]], color = "k")
		plt.plot(toyaVsReactionAve[~outlier_indicies,1], toyaVsReactionAve[~outlier_indicies,0], "ob", markeredgewidth=0.1, alpha=0.9)
		plt.plot(toyaVsReactionAve[outlier_indicies,1], toyaVsReactionAve[outlier_indicies,0], "o", color='#ed713a', markeredgewidth=0.1, alpha=0.9)
		plt.xlabel("Toya 2010 Reaction Flux [mmol/g/hr]")
		plt.ylabel("Mean WCM Reaction Flux [mmol/g/hr]")
		ax = plt.axes()
		whitePadSparklineAxis(ax)

		xlim = [-20, 30]
		ylim = [-20, 70]
		ax.set_xlim(xlim)
		ax.set_ylim(ylim)
		ax.set_xticks(range(int(xlim[0]), int(xlim[1]) + 1, 10))
		ax.set_yticks(range(int(ylim[0]), int(ylim[1]) + 1, 10))

		exportFigure(plt, plotOutDir, plotOutFileName, metadata)

		ax.set_xlabel("")
		ax.set_ylabel("")
		ax.set_title("")
		ax.set_xticklabels([])
		ax.set_yticklabels([])

		exportFigure(plt, plotOutDir, plotOutFileName + "_stripped", metadata)
		plt.close("all")


if __name__ == "__main__":
	Plot().cli()
