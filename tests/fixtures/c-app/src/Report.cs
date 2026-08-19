using System.Collections.Generic;

namespace Demo
{
    /// <summary>Serves user reports over HTTP.</summary>
    public class ReportController
    {
        private readonly ReportStore store;

        /// <summary>Wires the controller to its store.</summary>
        public ReportController(ReportStore store)
        {
            this.store = store;
        }

        /// <summary>Returns every report there is.</summary>
        [HttpGet("/reports")]
        public List<string> List()
        {
            return store.All();
        }

        /// <summary>Returns how many reports there are.</summary>
        public int Total() => store.All().Count;
    }

    /// <summary>Holds the reports.</summary>
    public class ReportStore
    {
        private readonly List<string> items = new List<string>();

        /// <summary>Returns every stored report.</summary>
        public List<string> All()
        {
            return items;
        }
    }
}
